from sqlalchemy.orm import Session
from typing import List, Optional
import re
import time
import logging
from app.models.chat import ChatSession, Message
from app.models.friend import Friend
from app.models.llm import LLMConfig
from app.schemas import chat as chat_schemas
from datetime import datetime, timedelta

# Initialize logger for this module
logger = logging.getLogger(__name__)

# SSE Debug logger
sse_logger = logging.getLogger("sse_debug")
sse_logger.setLevel(logging.DEBUG)
if not sse_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[SSE %(asctime)s.%(msecs)03d] %(message)s', datefmt='%H:%M:%S'))
    sse_logger.addHandler(handler)

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent, ResponseReasoningSummaryTextDeltaEvent
from agents import Agent, Runner, set_default_openai_client, set_default_openai_api
from agents.items import ReasoningItem
from agents.stream_events import RunItemStreamEvent

# --- Session Services ---

def get_sessions(db: Session, skip: int = 0, limit: int = 100) -> List[ChatSession]:
    """
    Get all active (non-deleted) chat sessions, ordered by update_time desc.
    """
    return (
        db.query(ChatSession)
        .filter(ChatSession.deleted == False)
        .order_by(ChatSession.update_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_session(db: Session, session_id: int) -> Optional[ChatSession]:
    """
    Get a specific chat session by ID.
    """
    return db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.deleted == False).first()

def create_session(db: Session, session_in: chat_schemas.ChatSessionCreate) -> ChatSession:
    """
    Create a new chat session.
    手动新建会话时，强制归档该好友现有的活跃会话。
    """
    # 检查是否存在未归档的活跃会话，仅提取 ID 列表
    existing_session_ids = [
        s.id for s in db.query(ChatSession.id)
        .filter(
            ChatSession.friend_id == session_in.friend_id,
            ChatSession.deleted == False,
            ChatSession.memory_generated == False
        )
        .all()
    ]
    
    # 强制归档所有旧会话
    for session_id in existing_session_ids:
        logger.info(f"[Create Session] Force archiving old session {session_id} for friend {session_in.friend_id}")
        archive_session(db, session_id)
    
    # 创建新会话
    db_session = ChatSession(
        friend_id=session_in.friend_id,
        title=session_in.title or "新对话"
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def update_session(db: Session, session_id: int, session_in: chat_schemas.ChatSessionUpdate) -> Optional[ChatSession]:
    """
    Update a chat session (e.g. title).
    """
    db_session = get_session(db, session_id)
    if not db_session:
        return None
    
    update_data = session_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_session, field, value)
    
    db.commit()
    db.refresh(db_session)
    return db_session

def delete_session(db: Session, session_id: int) -> bool:
    """
    Soft delete a chat session.
    """
    db_session = get_session(db, session_id)
    if not db_session:
        return False
    
    db_session.deleted = True
    db.commit()
    return True

# --- Message Services ---

def get_messages(db: Session, session_id: int, skip: int = 0, limit: int = 100) -> List[Message]:
    """
    Get messages for a specific session.
    """
    return (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.deleted == False)
        .order_by(Message.create_time.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_messages_by_friend(db: Session, friend_id: int, skip: int = 0, limit: int = 200) -> List[Message]:
    """
    Get all messages for a specific friend across all sessions.
    Messages are merged and sorted by create_time.
    """
    # Get all non-deleted sessions for this friend
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False)
        .all()
    )
    session_ids = [s.id for s in sessions]
    
    if not session_ids:
        return []
    
    # Get all messages from these sessions
    return (
        db.query(Message)
        .filter(Message.session_id.in_(session_ids), Message.deleted == False)
        .order_by(Message.create_time.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_sessions_by_friend(db: Session, friend_id: int) -> List[ChatSession]:
    """
    Get all sessions for a specific friend.
    """
    return (
        db.query(ChatSession)
        .filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False)
        .order_by(ChatSession.update_time.desc())
        .all()
    )

def get_or_create_session_for_friend(db: Session, friend_id: int) -> ChatSession:
    """
    获取好友最近的会话，如果已超时或不存在则创建新会话。
    """
    from app.services.settings_service import SettingsService
    timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)
    
    # 查找受该好友最近的一个非删除会话
    session = (
        db.query(ChatSession)
        .filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False)
        .order_by(ChatSession.update_time.desc())
        .first()
    )
    
    if session:
        # 判定是否超时
        if session.last_message_time:
            now_time = datetime.now()
            elapsed = (now_time - session.last_message_time).total_seconds()
            
            logger.info(f"[Session Check] Session {session.id} (Friend {friend_id}): Last msg {session.last_message_time}, Elapsed {elapsed:.1f}s, Timeout {timeout}s")
            
            if elapsed > timeout:
                logger.info(f"[Session Check] Session {session.id} EXPIRED. Triggering archive...")
                # 触发归档逻辑（异步或标记）
                archive_session(db, session.id)
                session = None # 强制进入下面的创建逻辑
            else:
                logger.info(f"[Session Check] Session {session.id} ACTIVE. Continuing.")
        else:
            logger.info(f"[Session Check] Session {session.id} has no last_message_time. Treated as ACTIVE/NEW.")
            # 如果没有 last_message_time，可能是一个刚创建的空会话，直接使用
            return session

    if not session:
        logger.info(f"[Session Check] Creating NEW session for friend {friend_id}...")
        # 创建新会话
        from app.schemas.chat import ChatSessionCreate
        session_in = ChatSessionCreate(friend_id=friend_id)
        session = create_session(db, session_in=session_in)
        logger.info(f"[Session Check] New session {session.id} created.")
    
    return session

def archive_session(db: Session, session_id: int):
    """
    将指定会话归档并准备生成记忆（同步版本）。
    - 消息数 < 2 的会话跳过记忆生成，仅标记为已处理。
    - 调用 Memobase SDK 异步生成记忆摘要。
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        logger.warning(f"[Archive] Session {session_id} not found.")
        return
    
    if session.memory_generated:
        logger.info(f"[Archive] Session {session_id} already archived (memory_generated=True). Skipping.")
        return

    # 边界检查：消息数 < 2 跳过
    msg_count = db.query(Message).filter(
        Message.session_id == session_id, 
        Message.deleted == False
    ).count()
    
    if msg_count < 2:
        session.memory_generated = True  # 标记为已处理但无需生成记忆
        db.commit()
        logger.info(f"[Archive] Session {session_id} skipped (msg_count={msg_count} < 2). Marked as processed.")
        return

    # 提取消息上下文
    messages = (
        db.query(Message)
        .filter(
            Message.session_id == session_id,
            Message.deleted == False,
            Message.role.in_(["user", "assistant"])
        )
        .order_by(Message.create_time.asc())
        .all()
    )
    
    # 格式化为 OpenAI 兼容格式
    openai_messages = [{"role": m.role, "content": m.content} for m in messages]
    
    # 获取好友信息用于 metadata
    friend = db.query(Friend).filter(Friend.id == session.friend_id).first()
    friend_id = session.friend_id
    friend_name = friend.name if friend else "Unknown"
    
    # 调用 Memobase SDK 异步任务（在后台执行）
    import asyncio
    loop = asyncio.get_running_loop()
    asyncio.create_task(_archive_session_async(
        session_id=session_id,
        openai_messages=openai_messages,
        friend_id=friend_id,
        friend_name=friend_name
    ))
    logger.info(f"[Archive] Session {session_id} memory generation task scheduled.")
    
    # 标记为已处理
    session.memory_generated = True
    db.commit()
    logger.info(f"[Archive] Session {session_id} marked as archived.")


async def _archive_session_async(
    session_id: int,
    openai_messages: List[dict],
    friend_id: int,
    friend_name: str
):
    """
    异步执行记忆生成任务。
    调用 Memobase SDK 插入聊天记录并触发摘要提取。
    """
    from app.services.memo.bridge import MemoService, MemoServiceException
    from app.vendor.memobase_server.models.blob import BlobType
    from datetime import datetime
    
    # 硬编码用户和空间 ID（单用户模式，未来需从 Session/Context 获取）
    user_id = "default_user"
    space_id = "default"
    
    try:
        # 1. 确保用户存在
        await MemoService.ensure_user(user_id=user_id, space_id=space_id)
        
        # 2. 插入聊天记录到 buffer，包含 metadata
        result = await MemoService.insert_chat(
            user_id=user_id,
            space_id=space_id,
            messages=openai_messages,
            fields={
                "friend_id": str(friend_id),
                "friend_name": friend_name,
                "session_id": str(session_id),
                "archived_at": datetime.now().isoformat()
            }
        )
        logger.info(f"[Archive Async] Session {session_id} chat inserted with metadata. Blob ID: {result.id if hasattr(result, 'id') else result}")
        
        # 3. 立即触发 buffer flush 以生成摘要
        await MemoService.trigger_buffer_flush(
            user_id=user_id,
            space_id=space_id,
            blob_type=BlobType.chat
        )
        logger.info(f"[Archive Async] Session {session_id} buffer flush triggered. Memory generation complete.")
        
    except MemoServiceException as e:
        logger.error(f"[Archive Async] Session {session_id} Memobase SDK error: {e}")
    except Exception as e:
        logger.error(f"[Archive Async] Session {session_id} unexpected error: {e}")

async def send_message(db: Session, session_id: int, message_in: chat_schemas.MessageCreate) -> Message:
    """
    Send a message (User) and get a real LLM response using openai-agents.
    """
    # 1. Verify session and fetch friend/config
    db_session = get_session(db, session_id)
    if not db_session:
        return None

    friend = db.query(Friend).filter(Friend.id == db_session.friend_id).first()
    system_prompt = friend.system_prompt if friend else "你是一名通用问答型 AI 助手。"

    llm_config = db.query(LLMConfig).filter(LLMConfig.deleted == False).order_by(LLMConfig.id.desc()).first()
    if not llm_config:
        # Fallback or error
        raise Exception("LLM configuration not found in database")

    # 2. Save User Message
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=message_in.content
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 3. Prepare LLM Context
    # Fetch history (last 10 messages for context)
    history = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.deleted == False, Message.id != user_msg.id)
        .order_by(Message.create_time.desc())
        .limit(10)
        .all()
    )
    history.reverse()

    agent_messages = []
    for m in history:
        agent_messages.append({"role": m.role, "content": m.content})
    
    # Add current user message to context
    agent_messages.append({"role": "user", "content": message_in.content})

    # 4. Call LLM via openai-agents
    client = AsyncOpenAI(
        base_url=llm_config.base_url,
        api_key=llm_config.api_key,
    )
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions")

    agent = Agent(
        name=friend.name if friend else "AI",
        instructions=system_prompt,
        model=llm_config.model_name
    )

    try:
        # Pass the full list of messages as input
        result = await Runner.run(agent, agent_messages)
        ai_content = result.final_output
        
        # Strip <think> tags from content before saving
        if ai_content:
            ai_content = re.sub(r'<think>.*?</think>', '', ai_content, flags=re.DOTALL)

    except Exception as e:
        ai_content = f"Error calling LLM: {str(e)}"

    # 5. Save AI Response
    ai_msg = Message(
        session_id=session_id,
        role="assistant",
        content=ai_content,
        friend_id=db_session.friend_id
    )
    db.add(ai_msg)
    
    # Update session update_time and last_message_time
    now = datetime.now()
    db_session.update_time = now
    db_session.last_message_time = now
    
    db.commit()
    db.refresh(ai_msg)

    return ai_msg

async def send_message_stream(db: Session, session_id: int, message_in: chat_schemas.MessageCreate):
    """
    Send a message (User) and stream the LLM response using SSE event structure.
    Yields dictionaries representing SSE events.
    """
    # 1. Verify session and fetch friend/config
    db_session = get_session(db, session_id)
    if not db_session:
        yield {"event": "error", "data": {"code": "session_not_found", "detail": "Session not found"}}
        return

    friend = db.query(Friend).filter(Friend.id == db_session.friend_id).first()
    system_prompt = friend.system_prompt if friend else "你是一名通用问答型 AI 助手。"
    friend_name = friend.name if friend else "AI"

    llm_config = db.query(LLMConfig).filter(LLMConfig.deleted == False).order_by(LLMConfig.id.desc()).first()
    if not llm_config:
        yield {"event": "error", "data": {"code": "config_not_found", "detail": "LLM configuration not found"}}
        return

    # 2. Save User Message
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=message_in.content
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 3. Prepare LLM Context
    history = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.deleted == False, Message.id != user_msg.id)
        .order_by(Message.create_time.desc())
        .limit(10)
        .all()
    )
    history.reverse()

    agent_messages = []
    for m in history:
        agent_messages.append({"role": m.role, "content": m.content})
    agent_messages.append({"role": "user", "content": message_in.content})

    # Yield Start Event
    # Create AI Message placeholder to get ID
    ai_msg = Message(
        session_id=session_id,
        role="assistant",
        content="", # Placeholder, will be updated
        friend_id=db_session.friend_id
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    yield {
        "event": "start",
        "data": {
            "session_id": session_id,
            "message_id": ai_msg.id,
            "user_message_id": user_msg.id,
            "model": llm_config.model_name,
            "friend_id": db_session.friend_id,
            "friend_name": friend_name,
            "created_at": datetime.now().isoformat()
        }
    }

    # 4. Call LLM via openai-agents
    client = AsyncOpenAI(
        base_url=llm_config.base_url,
        api_key=llm_config.api_key,
    )
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions")

    agent = Agent(
        name=friend_name,
        instructions=system_prompt,
        model=llm_config.model_name
    )

    full_ai_content = ""
    full_thinking_content = ""
    saved_content = ""
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    finish_reason = "stop"

    # Buffer for tag parsing
    buffer = ""
    is_thinking = False
    THINK_START = "<think>"
    THINK_END = "</think>"
    enable_thinking = message_in.enable_thinking

    # SSE timing debug
    sse_start_time = time.perf_counter()
    sse_frame_count = 0
    sse_first_frame_logged = False
    sse_logger.debug(f"[SESSION {session_id}] Starting LLM stream...")
    
    try:
        result = Runner.run_streamed(agent, agent_messages)
        sse_logger.debug(f"[SESSION {session_id}] Runner.run_streamed returned at {time.perf_counter() - sse_start_time:.3f}s")
        
        async for event in result.stream_events():
            elapsed = time.perf_counter() - sse_start_time
            if not sse_first_frame_logged:
                sse_logger.debug(f"[SESSION {session_id}] FIRST EVENT at {elapsed:.3f}s - type: {type(event).__name__}")
                sse_first_frame_logged = True
            
            # PRIORITY 1: Handle streaming reasoning delta events (REAL-TIME)
            # This catches reasoning tokens as they stream, BEFORE reasoning_item_created
            if event.type == "raw_response_event" and isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent):
                if enable_thinking:
                    reasoning_delta = event.data.delta
                    if reasoning_delta:
                        full_thinking_content += reasoning_delta
                        sse_frame_count += 1
                        sse_logger.debug(f"[SESSION {session_id}] YIELD thinking_delta #{sse_frame_count} at {time.perf_counter() - sse_start_time:.3f}s: {reasoning_delta[:30]}...")
                        yield {
                            "event": "thinking",
                            "data": {"delta": reasoning_delta}
                        }
                continue
            
            # PRIORITY 2: Handle reasoning item events (SUMMARY - arrives after all deltas)
            # Keep this for models that don't support streaming reasoning
            if isinstance(event, RunItemStreamEvent) and event.name == "reasoning_item_created":
                if enable_thinking and isinstance(event.item, ReasoningItem):
                    # Extract reasoning content from the raw item
                    raw_item = event.item.raw_item
                    reasoning_text = ""
                    
                    # 1. Handle GLM-style summary list
                    if hasattr(raw_item, 'summary') and raw_item.summary:
                        for summary_item in raw_item.summary:
                            if hasattr(summary_item, 'text'):
                                reasoning_text += summary_item.text
                            elif isinstance(summary_item, dict):
                                reasoning_text += summary_item.get('text', '')
                    
                    # 2. Handle standard content field
                    elif hasattr(raw_item, 'content') and raw_item.content:
                        reasoning_text = raw_item.content
                    
                    # 3. Handle dict-style
                    elif isinstance(raw_item, dict):
                        reasoning_text = raw_item.get('content', '') or raw_item.get('summary', '')
                    
                    if reasoning_text:
                        full_thinking_content += reasoning_text
                        sse_frame_count += 1
                        sse_logger.debug(f"[SESSION {session_id}] YIELD thinking #{sse_frame_count} at {time.perf_counter() - sse_start_time:.3f}s: {reasoning_text[:30]}...")
                        yield {
                            "event": "thinking",
                            "data": {"delta": reasoning_text}
                        }
                continue
            
            # Handle text delta events (with <think> tag parsing for models like DeepSeek-R1)
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                delta = event.data.delta
                if delta:
                    full_ai_content += delta
                    buffer += delta

                    while buffer:
                        if not is_thinking:
                            # Look for <think>
                            start_idx = buffer.find(THINK_START)
                            if start_idx != -1:
                                # Yield content before tag as message
                                if start_idx > 0:
                                    msg_delta = buffer[:start_idx]
                                    saved_content += msg_delta
                                    sse_frame_count += 1
                                    sse_logger.debug(f"[SESSION {session_id}] YIELD message #{sse_frame_count} at {time.perf_counter() - sse_start_time:.3f}s: {msg_delta[:30]}...")
                                    yield {
                                        "event": "message",
                                        "data": {"delta": msg_delta}
                                    }
                                buffer = buffer[start_idx + len(THINK_START):]
                                is_thinking = True
                                # If thinking mode disabled, skip thinking content silently
                            else:
                                # Check partial tag
                                partial_len = 0
                                for i in range(1, len(THINK_START)):
                                    if buffer.endswith(THINK_START[:i]):
                                        partial_len = i
                                
                                if partial_len > 0:
                                    # Yield everything up to partial
                                    to_yield = buffer[:-partial_len]
                                    buffer = buffer[-partial_len:]
                                    if to_yield:
                                        saved_content += to_yield
                                        yield {"event": "message", "data": {"delta": to_yield}}
                                    break  # Wait for more data
                                else:
                                    # Yield all
                                    saved_content += buffer
                                    sse_frame_count += 1
                                    sse_logger.debug(f"[SESSION {session_id}] YIELD message #{sse_frame_count} at {time.perf_counter() - sse_start_time:.3f}s: {buffer[:30]}...")
                                    yield {"event": "message", "data": {"delta": buffer}}
                                    buffer = ""
                        else:
                            # Look for </think>
                            end_idx = buffer.find(THINK_END)
                            if end_idx != -1:
                                # Yield content before tag as thinking (only if enabled)
                                if end_idx > 0 and enable_thinking:
                                    yield {
                                        "event": "thinking",
                                        "data": {"delta": buffer[:end_idx]}
                                    }
                                buffer = buffer[end_idx + len(THINK_END):]
                                is_thinking = False
                            else:
                                # Check partial end tag
                                partial_len = 0
                                for i in range(1, len(THINK_END)):
                                    if buffer.endswith(THINK_END[:i]):
                                        partial_len = i
                                
                                if partial_len > 0:
                                    to_yield = buffer[:-partial_len]
                                    buffer = buffer[-partial_len:]
                                    if to_yield and enable_thinking:
                                        yield {"event": "thinking", "data": {"delta": to_yield}}
                                    break
                                else:
                                    if enable_thinking:
                                        yield {"event": "thinking", "data": {"delta": buffer}}
                                    buffer = ""
        
        # Flush remaining buffer
        if buffer:
            if is_thinking and enable_thinking:
                yield {"event": "thinking", "data": {"delta": buffer}}
            elif not is_thinking:
                saved_content += buffer
                yield {"event": "message", "data": {"delta": buffer}}

    except Exception as e:
        # LLM call failed - yield error event
        error_message = str(e)
        yield {
            "event": "error",
            "data": {
                "code": "llm_error",
                "detail": f"LLM 调用失败: {error_message}"
            }
        }
        finish_reason = "error"
        # Store error message as AI response
        full_ai_content = f"[Error: {error_message}]"

    # 5. Save AI Response once finished
    # Only save the cleaned message content (excluding reasoning)
    ai_msg.content = saved_content if saved_content else "[No response]"
    now = datetime.now()
    db_session.update_time = now
    db_session.last_message_time = now
    db.commit()
    db.refresh(ai_msg)

    # Always yield Done Event
    usage["completion_tokens"] = len(full_ai_content)
    
    yield {
        "event": "done",
        "data": {
            "finish_reason": finish_reason,
            "usage": usage,
            "message_id": ai_msg.id
        }
    }

def check_and_archive_expired_sessions(db: Session) -> int:
    """
    检查并归档所有过期的会话。
    用于后台定时任务。
    """
    from app.services.settings_service import SettingsService
    timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)
    
    # Calculate threshold time
    threshold_time = datetime.now() - timedelta(seconds=timeout)
    
    # Query candidate sessions
    # memory_generated = False AND deleted = False AND last_message_time < threshold
    # 注意：last_message_time 为 NULL 的会话（新建但无消息）会被自动过滤，符合预期
    candidates = (
        db.query(ChatSession)
        .filter(
            ChatSession.memory_generated == False,
            ChatSession.deleted == False,
            ChatSession.last_message_time < threshold_time  # NULL 值自动过滤
        )
        .all()
    )
    
    if not candidates:
        return 0
        
    logger.info(f"[Background Task] Found {len(candidates)} expired sessions. Archiving...")
    
    count = 0
    for session in candidates:
        try:
            archive_session(db, session.id)
            count += 1
        except Exception as e:
            logger.error(f"[Background Task] Error archiving session {session.id}: {str(e)}")
            
    return count
