from sqlalchemy.orm import Session
from typing import List, Optional
import re
import json
import time
import logging
import asyncio
from asyncio import Queue
from app.models.chat import ChatSession, Message
from app.models.friend import Friend
from app.schemas import chat as chat_schemas
from datetime import datetime, timedelta, timezone
from app.services.recall_service import RecallService
from app.services.settings_service import SettingsService
from app.services import provider_rules
from app.services.llm_service import llm_service
from app.services.embedding_service import embedding_service
from app.services.memo.bridge import MemoService
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.prompt import get_prompt
from app.db.session import SessionLocal
import re

def _strip_message_tags(content: Optional[str]) -> Optional[str]:
    if not content:
        return content
    # 提取所有 <message> 标签内容并用空格合并
    parts = re.findall(r'<message>(.*?)</message>', content, re.DOTALL)
    if parts:
        return " ".join(part.strip() for part in parts if part.strip())
    # 兜底：如果没有匹配到完整标签但包含标签字符，直接剔除所有标签文本
    return re.sub(r'</?message>', '', content).strip()

def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    return model_name.split("/", 1)[-1].lower()

def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")

def _extract_reasoning_text(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw

    def _collect_text(value: object) -> List[str]:
        texts: List[str] = []
        if not value:
            return texts
        if isinstance(value, (list, tuple)):
            for entry in value:
                texts.extend(_collect_text(entry))
            return texts
        if isinstance(value, dict):
            text = value.get("text") or value.get("content")
            if text:
                texts.append(str(text))
            return texts
        text = getattr(value, "text", None) or getattr(value, "content", None)
        if text:
            texts.append(str(text))
        return texts

    if isinstance(raw, dict):
        text = raw.get("reasoning_content") or raw.get("reasoning") or raw.get("text")
        if text:
            return str(text)
        content = raw.get("content")
        summary = raw.get("summary")
    else:
        text = getattr(raw, "reasoning_content", None) or getattr(raw, "reasoning", None) or getattr(raw, "text", None)
        if text:
            return str(text)
        content = getattr(raw, "content", None)
        summary = getattr(raw, "summary", None)

    texts = _collect_text(content)
    if not texts:
        texts = _collect_text(summary)
    return "\n".join([t for t in texts if t])

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
from openai.types.shared import Reasoning
from openai.types.responses import (
    ResponseOutputText,
    ResponseTextDeltaEvent,
)
from agents import Agent, ModelSettings, RunConfig, Runner, function_tool, set_default_openai_client, set_default_openai_api
from agents.items import MessageOutputItem, ReasoningItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent

# Global queue for memory generation tasks (processed by background worker)
_memory_generation_queue: List[int] = []

def _schedule_memory_generation(db: Session, session_id: int):
    """
    调度一个会话的记忆生成任务。
    由于在同步上下文中无法直接创建异步任务，这里将session_id添加到全局队列。
    后台worker会定期检查队列并异步处理。
    """
    if session_id not in _memory_generation_queue:
        _memory_generation_queue.append(session_id)
        logger.info(f"[Memory Queue] Session {session_id} added to memory generation queue. Queue size: {len(_memory_generation_queue)}")
    
    # 尝试直接调度异步任务（如果当前在主线程/有运行中的 loop）
    try:
        loop = asyncio.get_running_loop()
        # 如果 loop 正在运行，尝试在该 loop 中创建任务
        # 注意：此处准备数据以传递给异步函数
        messages = db.query(Message).filter(Message.session_id == session_id, Message.deleted == False).order_by(Message.create_time.asc()).all()
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session: return
        friend = db.query(Friend).filter(Friend.id == session.friend_id).first()
        
        openai_messages = [{"role": m.role, "content": m.content} for m in messages]
        
        # 使用 call_soon_threadsafe 或直接 create_task
        # 如果在主线程，直接 create_task
        loop.create_task(_archive_session_async(
            session_id=session_id,
            openai_messages=openai_messages,
            friend_id=session.friend_id,
            friend_name=friend.name if friend else "Unknown"
        ))
        logger.info(f"[Memory Queue] Session {session_id} async task created directly via running loop.")
        # 从队列中移除，因为已经成功调度
        if session_id in _memory_generation_queue:
            _memory_generation_queue.remove(session_id)
    except RuntimeError:
        # 没有运行中的循环，保留在队列中等待后台 worker
        logger.info(f"[Memory Queue] No running loop. Session {session_id} stays in queue for background worker.")

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
    手动新建会话时，如果已经存在一个没有任何消息的活跃会话，则直接返回该会话；
    否则，强制归档该好友现有的活跃会话，并创建新会话。
    """
    # 查找该好友所有活跃（未删除、未归档）的会话
    active_sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.friend_id == session_in.friend_id,
            ChatSession.deleted == False,
            ChatSession.memory_generated == 0
        )
        .all()
    )

    # 优先检查是否存在没有任何消息的空活跃会话
    for session in active_sessions:
        msg_count = db.query(Message).filter(Message.session_id == session.id, Message.deleted == False).count()
        if msg_count == 0:
            logger.info(f"[Create Session] Reusing existing empty session {session.id} for friend {session_in.friend_id}")
            # 如果请求带了新标题，则更新标题
            if session_in.title and session.title != session_in.title:
                session.title = session_in.title
                db.commit()
                db.refresh(session)
            return session

    # 如果没有空会话，强制归档所有旧活跃会话
    for session in active_sessions:
        logger.info(f"[Create Session] Force archiving session {session.id} for friend {session_in.friend_id} before creating new one")
        archive_session(db, session.id)
    
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
    Soft delete a chat session and cascade delete its memories.
    """
    db_session = get_session(db, session_id)
    if not db_session:
        return False
    
    # 1. Soft delete session
    db_session.deleted = True
    db.commit()

    # 2. Schedule memory deletion
    _schedule_session_memory_deletion(session_id)
    
    return True

def clear_friend_chat_history(db: Session, friend_id: int):
    """
    清空与指定好友的所有聊天记录，并在清空前尝试归档现有记忆。
    同时删除 Memobase 中与该好友相关的 events 和 event_gists。
    """
    # 1. 找到该好友所有未归档且未删除的会话
    sessions = db.query(ChatSession).filter(
        ChatSession.friend_id == friend_id,
        ChatSession.deleted == False
    ).all()
    
    for session in sessions:
        # 如果该会话尚未生成记忆，且包含至少2条消息，触发归档
        if session.memory_generated == 0:
            msg_count = db.query(Message).filter(
                Message.session_id == session.id,
                Message.deleted == False
            ).count()
            if msg_count >= 2:
                logger.info(f"[Clear History] Archiving session {session.id} before deletion.")
                archive_session(db, session.id)
            else:
                # 消息太少，直接标记为已生成记忆以便不再扫描
                session.memory_generated = 1
        
        # 2. 标记会话为已删除
        session.deleted = True
        
        # 3. 标记该会话下的所有消息为已删除
        db.query(Message).filter(Message.session_id == session.id).update({"deleted": True})
    
    db.commit()
    logger.info(f"[Clear History] All chat history for friend {friend_id} has been cleared/archived.")
    
    # 4. 调度 Memobase 记忆删除任务
    _schedule_memory_deletion(friend_id)

def _schedule_memory_deletion(friend_id: int):
    """
    调度删除 Memobase 中与指定好友相关的记忆。
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_delete_friend_memories_async(friend_id))
        logger.info(f"[Memory Deletion] Scheduled deletion for friend {friend_id}")
    except RuntimeError:
        # 没有运行中的事件循环，使用线程池执行
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(_run_delete_friend_memories_sync, friend_id)
        logger.info(f"[Memory Deletion] Scheduled deletion (via thread) for friend {friend_id}")

def _run_delete_friend_memories_sync(friend_id: int):
    """
    在新的事件循环中执行记忆删除（用于没有运行中 loop 的情况）。
    """
    asyncio.run(_delete_friend_memories_async(friend_id))

async def _delete_friend_memories_async(friend_id: int):
    """
    异步删除 Memobase 中与指定好友相关的记忆。
    """
    from app.services.memo.bridge import MemoService, MemoServiceException
    from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
    
    try:
        count = await MemoService.delete_friend_memories(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            friend_id=friend_id
        )
        logger.info(f"[Memory Deletion] Successfully deleted {count} events for friend {friend_id}")
    except MemoServiceException as e:
        logger.error(f"[Memory Deletion] Failed to delete memories for friend {friend_id}: {e}")
    except Exception as e:
        logger.error(f"[Memory Deletion] Unexpected error for friend {friend_id}: {e}")

# --- Session Memory Deletion Helpers ---

def _schedule_session_memory_deletion(session_id: int):
    """
    调度删除 Memobase 中与指定 session 相关的记忆。
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_delete_session_memories_async(session_id))
        logger.info(f"[Memory Deletion] Scheduled deletion for session {session_id}")
    except RuntimeError:
        # 没有运行中的事件循环，使用线程池执行
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(_run_delete_session_memories_sync, session_id)
        logger.info(f"[Memory Deletion] Scheduled deletion (via thread) for session {session_id}")

def _run_delete_session_memories_sync(session_id: int):
    asyncio.run(_delete_session_memories_async(session_id))

async def _delete_session_memories_async(session_id: int):
    from app.services.memo.bridge import MemoService, MemoServiceException
    from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
    
    try:
        count = await MemoService.delete_session_memories(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            session_id=session_id
        )
        logger.info(f"[Memory Deletion] Successfully deleted {count} events for session {session_id}")
    except MemoServiceException as e:
        logger.error(f"[Memory Deletion] Failed to delete memories for session {session_id}: {e}")
    except Exception as e:
        logger.error(f"[Memory Deletion] Unexpected error for session {session_id}: {e}")

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
    
    NOTE: To support pagination correctly (newest messages first for initial load),
    we query in DESC order and then reverse the result.
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
    
    # Get messages in DESC order (newest first) for pagination, then reverse
    messages = (
        db.query(Message)
        .filter(Message.session_id.in_(session_ids), Message.deleted == False)
        .order_by(Message.create_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    # Reverse to display in chronological order (oldest to newest)
    return list(reversed(messages))

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

def get_sessions_with_stats_by_friend(db: Session, friend_id: int) -> List[dict]:
    """
    获取指定好友的所有会话，包含消息计数和预览，已优化性能。
    """
    from sqlalchemy import func
    
    # 按照最近更新时间倒序获取会话
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False)
        .order_by(ChatSession.update_time.desc())
        .all()
    )
    
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    
    # 批量获取所有会话的消息计数
    counts_query = (
        db.query(Message.session_id, func.count(Message.id).label('count'))
        .filter(Message.session_id.in_(session_ids), Message.deleted == False)
        .group_by(Message.session_id)
        .all()
    )
    counts_map = {row.session_id: row.count for row in counts_query}

    # 批量获取每个会话的第一条用户消息作为预览
    first_user_msg_ids_subq = (
        db.query(Message.session_id, func.min(Message.id).label('min_id'))
        .filter(
            Message.session_id.in_(session_ids), 
            Message.deleted == False,
            Message.role == 'user'
        )
        .group_by(Message.session_id)
        .subquery()
    )
    
    previews_map = {}
    first_user_messages = (
        db.query(Message)
        .join(first_user_msg_ids_subq, Message.id == first_user_msg_ids_subq.c.min_id)
        .all()
    )
    for msg in first_user_messages:
        content = _strip_message_tags(msg.content)
        text = content[:50].strip().replace('\n', ' ')
        previews_map[msg.session_id] = f"{text}{'...' if len(content) > 50 else ''}"

    # 对于没有用户消息的会话（如全系统消息），回退到最后一条消息
    remaining_session_ids = [sid for sid in session_ids if sid not in previews_map]
    if remaining_session_ids:
        latest_msg_ids_subq = (
            db.query(Message.session_id, func.max(Message.id).label('max_id'))
            .filter(Message.session_id.in_(remaining_session_ids), Message.deleted == False)
            .group_by(Message.session_id)
            .subquery()
        )
        latest_messages = (
            db.query(Message)
            .join(latest_msg_ids_subq, Message.id == latest_msg_ids_subq.c.max_id)
            .all()
        )
        for msg in latest_messages:
            role_name = "AI" if msg.role == "assistant" else ("系统" if msg.role == "system" else "我")
            content = _strip_message_tags(msg.content)
            text = content[:50].strip().replace('\n', ' ')
            previews_map[msg.session_id] = f"{role_name}: {text}{'...' if len(content) > 50 else ''}"

    # 第一个是活跃会话（因为按 update_time 倒序排列）
    active_session_id = sessions[0].id

    result = []
    for s in sessions:
        res_dict = {
            "id": s.id,
            "friend_id": s.friend_id,
            "title": s.title,
            "create_time": s.create_time,
            "update_time": s.update_time,
            "deleted": s.deleted,
            "memory_generated": s.memory_generated,
            "memory_error": s.memory_error,
            "last_message_time": s.last_message_time or s.update_time,
            "message_count": counts_map.get(s.id, 0),
            "last_message_preview": previews_map.get(s.id, ""),
            "is_active": s.id == active_session_id
        }
        result.append(res_dict)
        
    return result

def get_or_create_session_for_friend(db: Session, friend_id: int) -> ChatSession:
    """
    获取好友最近的会话，如果已超时或不存在则创建新会话。
    优先返回最新创建的会话（ID最大），而不是最近更新的会话。
    """
    from app.services.settings_service import SettingsService
    timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)

    # 查找受该好友最近的一个非删除、未归档会话
    # 按 ID 倒序（最新创建的在前）以确保获取的是最新会话
    session = (
        db.query(ChatSession)
        .filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False, ChatSession.memory_generated == 0)
        .order_by(ChatSession.id.desc())
        .first()
    )
    
    if session:
        # 判定是否超时
        if session.last_message_time:
            now_time = datetime.now(timezone.utc)
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
    - 标记会话为已归档，实际记忆生成由后台任务统一处理。
    - 更新 update_time 以防止被误选为活跃会话。
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        logger.warning(f"[Archive] Session {session_id} not found.")
        return

    if session.memory_generated == 1:
        logger.info(f"[Archive] Session {session_id} already archived (memory_generated=1). Skipping.")
        return

    # 边界检查:消息数 < 2 跳过
    msg_count = db.query(Message).filter(
        Message.session_id == session_id,
        Message.deleted == False
    ).count()

    if msg_count < 2:
        session.memory_generated = 1  # 标记为已处理但无需生成记忆
        session.update_time = datetime.now(timezone.utc)  # 更新时间以确保不会误选
        db.commit()
        logger.info(f"[Archive] Session {session_id} skipped (msg_count={msg_count} < 2). Marked as processed.")
        return

    # 检查向量化配置
    embedding_config = embedding_service.get_active_setting(db)
    if not embedding_config:
        session.memory_generated = 2
        session.memory_error = "向量化未设置，无法生成记忆"
        session.update_time = datetime.now(timezone.utc)
        db.commit()
        logger.warning(f"[Archive] Session {session_id} archived without memory generation (Missing Embedding Config).")
        return

    # 标记为处理中（实际记忆生成由后台任务统一处理，完成后会设置最终状态）
    # 状态 3 = 处理中，防止 session 被误选
    session.memory_generated = 3
    session.update_time = datetime.now(timezone.utc)  # 更新时间以确保不会误选
    db.commit()
    logger.info(f"[Archive] Session {session_id} marked as processing (status=3). Memory generation scheduled.")
    
    # 将任务添加到全局队列供后台处理（避免同步上下文中调用 asyncio）
    _schedule_memory_generation(db, session_id)


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
    from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
    from app.vendor.memobase_server.models.blob import BlobType
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # 1. 确保用户存在
        await MemoService.ensure_user(user_id=DEFAULT_USER_ID, space_id=DEFAULT_SPACE_ID)
        
        # 2. 插入聊天记录到 buffer，包含 metadata
        result = await MemoService.insert_chat(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            messages=openai_messages,
            fields={
                "friend_id": str(friend_id),
                "friend_name": friend_name,
                "session_id": str(session_id),
                "archived_at": datetime.now(timezone.utc).isoformat()
            }
        )
        logger.info(f"[Archive Async] Session {session_id} chat inserted with metadata. Blob ID: {result.id if hasattr(result, 'id') else result}")
        
        # 3. 立即触发 buffer flush 以生成摘要
        is_ok, error_msg = await MemoService.trigger_buffer_flush(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            blob_type=BlobType.chat
        )
        logger.info(f"[Archive Async] Session {session_id} buffer flush completed. is_ok={is_ok}")
        
        # 4. 根据 flush 结果更新状态
        sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if sess:
            if is_ok:
                # Success: Update status to 1 (Generated)
                sess.memory_generated = 1
                sess.memory_error = None
                logger.info(f"[Archive Async] Session {session_id} memory generation complete (status=1).")
            else:
                # Embedding failed: Update status to 2 (Failed)
                sess.memory_generated = 2
                sess.memory_error = error_msg
                logger.warning(f"[Archive Async] Session {session_id} embedding failed (status=2): {error_msg}")
            db.commit()
        
    except MemoServiceException as e:
        logger.error(f"[Archive Async] Session {session_id} Memobase SDK error: {e}")
        # Failure: Update status to 2 (Failed) and save error
        sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if sess:
            sess.memory_generated = 2
            sess.memory_error = f"SDK Error: {str(e)}"
            db.commit()
    except Exception as e:
        logger.error(f"[Archive Async] Session {session_id} unexpected error: {e}")
        # Failure: Update status to 2 (Failed) and save error
        sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if sess:
            sess.memory_generated = 2
            sess.memory_error = f"Unexpected Error: {str(e)}"
            db.commit()
    finally:
        db.close()

async def _run_chat_generation_task(
    session_id: int,
    friend_id: int,
    user_msg_id: int,
    ai_msg_id: int,
    message_content: str,
    enable_thinking: bool,
    queue: asyncio.Queue
):
    """
    Background task to handle LLM generation and persistence.
    Decoupled from HTTP response to ensure completion even if client disconnects.
    """
    db = SessionLocal()
    logger.info(f"[GenTask] Starting generation for Session {session_id}, AI Msg {ai_msg_id}")
    
    try:
        # 1. Fetch Context Data
        chat_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        friend = db.query(Friend).filter(Friend.id == friend_id).first()
        friend_name = friend.name if friend else "AI"
        
        llm_config = llm_service.get_active_config(db)
        if not llm_config:
            await queue.put({"event": "error", "data": {"code": "config_error", "detail": "LLM Config missing in background task"}})
            return

        raw_model_name = llm_config.model_name
        model_name = llm_service.normalize_model_name(raw_model_name)
        force_thinking = provider_rules.is_gemini_model(llm_config, raw_model_name)
        if enable_thinking and not llm_config.capability_reasoning and not force_thinking:
            enable_thinking = False

        # 2. Prepare History & Recall
        enable_recall = SettingsService.get_setting(db, "memory", "recall_enabled", True)

        # Check for vectorization config
        if enable_recall:
            embedding_config = embedding_service.get_active_setting(db)
            if not embedding_config:
                logger.warning("[GenTask] Recall skipped: Embedding not configured.")
                enable_recall = False

        show_thinking = enable_thinking
        
        history = (
            db.query(Message)
            .filter(
                Message.session_id == session_id, 
                Message.deleted == False, 
                Message.id != user_msg_id,
                Message.id != ai_msg_id
            )
            .order_by(Message.create_time.desc())
            .limit(10)
            .all()
        )
        history.reverse()
        
        profile_data = ""
        injected_recall_messages = []
        
        if enable_recall:
            try:
                profiles = await MemoService.get_user_profiles(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
                if profiles and profiles.profiles:
                    profile_lines = []
                    for item in profiles.profiles:
                        if not item or not item.content: continue
                        attributes = item.attributes or {}
                        topic = (attributes.get("topic") or "").strip()
                        sub_topic = (attributes.get("sub_topic") or "").strip()
                        if topic or sub_topic:
                            profile_lines.append(f"- {topic}\t{sub_topic}\t{item.content.strip()}")
                        else:
                            profile_lines.append(f"- {item.content.strip()}")
                    profile_data = "\n".join(profile_lines)
                
                messages_for_recall = [{"role": m.role, "content": m.content} for m in history]
                messages_for_recall.append({"role": "user", "content": message_content})
                
                recall_result = await RecallService.perform_recall(
                    db, DEFAULT_USER_ID, DEFAULT_SPACE_ID, messages_for_recall, friend_id
                )
                injected_recall_messages = recall_result.get("injected_messages", [])
                footprints = recall_result.get("footprints", [])
                
                for fp in footprints:
                    if fp["type"] == "thinking" and show_thinking:
                        await queue.put({"event": "recall_thinking", "data": {"delta": f"> {fp['content']}\n"}})
                    elif fp["type"] == "tool_call":
                        await queue.put({"event": "tool_call", "data": {"tool_name": fp["name"], "arguments": fp["arguments"]}})
                    elif fp["type"] == "tool_result":
                        await queue.put({"event": "tool_result", "data": {"tool_name": fp["name"], "result": fp["result"]}})
            except Exception as e:
                error_detail = f"记忆召回失败: {e}"
                logger.error(f"[GenTask] Recall failed: {e}")
                ai_msg = db.query(Message).filter(Message.id == ai_msg_id).first()
                if ai_msg:
                    ai_msg.content = f"[错误] {error_detail}"
                    db.commit()
                    chat_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                    if chat_session:
                        chat_session.update_time = datetime.now(timezone.utc)
                        chat_session.last_message_time = datetime.now(timezone.utc)
                        if chat_session.memory_generated != 0:
                            chat_session.memory_generated = 0
                            chat_session.memory_error = None
                        db.commit()
                await queue.put({"event": "error", "data": {"code": "recall_error", "detail": error_detail}})
                return

        # 3. Construct Prompt
        # 内部使用 UTC，但喂给 LLM 的提示词应使用北京时间（UTC+8）
        beijing_tz = timezone(timedelta(hours=8))
        now_time = datetime.now(timezone.utc).astimezone(beijing_tz)
        
        weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        current_time = f"{now_time:%Y-%m-%d 约%H}点 {weekday_map[now_time.weekday()]}"
        
        persona_prompt = (friend.system_prompt if friend and friend.system_prompt else get_prompt("chat/default_system_prompt.txt"))
        if persona_prompt:
            persona_prompt = persona_prompt.strip()
        else:
            persona_prompt = ""
        
        script_prompt = ""
        if friend and friend.script_expression:
            try:
                script_prompt = get_prompt("persona/script_expression.txt").strip()
            except Exception:
                pass

        segment_prompt = ""
        try:
            if friend and friend.script_expression:
                segment_prompt = get_prompt("chat/message_segment_script.txt").strip()
            else:
                segment_prompt = get_prompt("chat/message_segment_normal.txt").strip()
        except Exception:
            pass

        try:
            root_template = get_prompt("chat/root_system_prompt.txt")
            final_instructions = root_template.replace("{{role-play-prompt}}", persona_prompt)
            final_instructions = final_instructions.replace("{{script-expression}}", f"\n\n{script_prompt}" if script_prompt else "")
            final_instructions = final_instructions.replace("{{user-profile}}", f"\n\n【用户信息】\n{profile_data}" if profile_data else "")
            final_instructions = final_instructions.replace("{{segment-instruction}}", f"\n\n{segment_prompt}" if segment_prompt else "")
            final_instructions = final_instructions.replace("{{current-time}}", current_time)
        except Exception:
            final_instructions = persona_prompt
            if script_prompt: final_instructions += f"\n\n{script_prompt}"
            if profile_data: final_instructions += f"\n\n【用户信息】\n{profile_data}"
            if segment_prompt: final_instructions += f"\n\n{segment_prompt}"
            final_instructions += f"\n\n【当前时间】\n{current_time}"

        tool_description = ""
        try:
            tool_description = get_prompt("recall/recall_tool_description.txt").strip()
        except Exception:
            pass

        @function_tool(name_override="recall_memory", description_override=tool_description)
        async def tool_recall(query: str):
            if not enable_recall:
                return {"events": []}
            if not embedding_service.get_active_setting(db):
                return {"events": []}
            event_topk = SettingsService.get_setting(db, "memory", "event_topk", 5)
            threshold = SettingsService.get_setting(db, "memory", "similarity_threshold", 0.5)
            return await MemoService.recall_memory(
                user_id=DEFAULT_USER_ID,
                space_id=DEFAULT_SPACE_ID,
                query=query,
                friend_id=friend_id,
                topk_event=event_topk,
                threshold=threshold,
            )

        # 4. Run LLM
        agent_messages = [{"role": m.role, "content": m.content} for m in history]
        inject_as_tool = any(
            isinstance(msg, dict) and msg.get("type") in ("function_call", "function_call_output")
            for msg in injected_recall_messages
        )
        if injected_recall_messages and not inject_as_tool:
            agent_messages.extend(injected_recall_messages)
        agent_messages.append({"role": "user", "content": message_content})
        if injected_recall_messages and inject_as_tool:
            agent_messages.extend(injected_recall_messages)

        client = AsyncOpenAI(base_url=llm_config.base_url, api_key=llm_config.api_key)
        set_default_openai_client(client, use_for_tracing=True)
        set_default_openai_api("chat_completions")

        temperature = friend.temperature if friend and friend.temperature is not None else 0.8
        top_p = friend.top_p if friend and friend.top_p is not None else 0.9

        use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
        model_settings_kwargs = {}
        if _supports_sampling(model_name):
            model_settings_kwargs["temperature"] = temperature
            model_settings_kwargs["top_p"] = top_p
        if (
            llm_config.capability_reasoning
            and not use_litellm
            and provider_rules.supports_reasoning_effort(llm_config)
        ):
            model_settings_kwargs["reasoning"] = Reasoning(
                effort="low" if enable_thinking else "none"
            )
        if use_litellm and enable_thinking:
            model_settings_kwargs["reasoning"] = Reasoning(effort="low")
        model_settings = ModelSettings(**model_settings_kwargs)
        if use_litellm:
            from agents.extensions.models.litellm_model import LitellmModel

            gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
            gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
            agent_model = LitellmModel(
                model=gemini_model_name,
                base_url=gemini_base_url,
                api_key=llm_config.api_key,
            )
        else:
            agent_model = model_name
        agent = Agent(
            name=friend_name,
            instructions=final_instructions,
            model=agent_model,
            model_settings=model_settings,
            tools=[tool_recall],
        )

        full_ai_content = ""
        saved_content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        finish_reason = "stop"
        
        buffer = ""
        is_thinking_tag = False
        has_reasoning_item = False
        think_fallback_buffer = ""
        tool_call_names = {}
        THINK_START = "<think>"
        THINK_END = "</think>"
        
        result = Runner.run_streamed(
            agent,
            agent_messages,
            run_config=RunConfig(trace_include_sensitive_data=True),
        )
        async for event in result.stream_events():
            if isinstance(event, RunItemStreamEvent) and event.name == "reasoning_item_created":
                if enable_thinking and isinstance(event.item, ReasoningItem):
                    has_reasoning_item = True
                    raw = event.item.raw_item
                    text = _extract_reasoning_text(raw)
                    if text:
                        await queue.put({"event": "model_thinking", "data": {"delta": text}})
                continue
            if isinstance(event, RunItemStreamEvent) and event.name == "tool_called":
                if isinstance(event.item, ToolCallItem):
                    raw = event.item.raw_item
                    if isinstance(raw, dict):
                        name = raw.get("name")
                        call_id = raw.get("call_id")
                        arguments = raw.get("arguments")
                    else:
                        name = getattr(raw, "name", None)
                        call_id = getattr(raw, "call_id", None)
                        arguments = getattr(raw, "arguments", None)
                    if call_id and name:
                        tool_call_names[call_id] = name
                    await queue.put({
                        "event": "tool_call",
                        "data": {
                            "tool_name": name or "tool",
                            "arguments": arguments,
                            "call_id": call_id,
                        },
                    })
                continue
            if isinstance(event, RunItemStreamEvent) and event.name == "tool_output":
                if isinstance(event.item, ToolCallOutputItem):
                    raw = event.item.raw_item
                    if isinstance(raw, dict):
                        call_id = raw.get("call_id")
                    else:
                        call_id = getattr(raw, "call_id", None)
                    name = tool_call_names.get(call_id, "tool")
                    await queue.put({
                        "event": "tool_result",
                        "data": {
                            "tool_name": name,
                            "result": event.item.output,
                            "call_id": call_id,
                        },
                    })
                continue

            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                delta = event.data.delta
                if delta:
                    full_ai_content += delta
                    buffer += delta
                    while buffer:
                        if not is_thinking_tag:
                            start_idx = buffer.find(THINK_START)
                            if start_idx != -1:
                                if start_idx > 0:
                                    msg_delta = buffer[:start_idx]
                                    saved_content += msg_delta
                                    await queue.put({"event": "message", "data": {"delta": msg_delta}})
                                buffer = buffer[start_idx + len(THINK_START):]
                                is_thinking_tag = True
                            else:
                                if "<" not in buffer:
                                    saved_content += buffer
                                    await queue.put({"event": "message", "data": {"delta": buffer}})
                                    buffer = ""
                                else:
                                    break
                        else:
                            end_idx = buffer.find(THINK_END)
                            if end_idx != -1:
                                if end_idx > 0 and enable_thinking and not has_reasoning_item:
                                    think_fallback_buffer += buffer[:end_idx]
                                buffer = buffer[end_idx + len(THINK_END):]
                                is_thinking_tag = False
                            else:
                                if "</" not in buffer:
                                    if enable_thinking and not has_reasoning_item:
                                        think_fallback_buffer += buffer
                                    buffer = ""
                                else:
                                    break
        
        if buffer:
            if is_thinking_tag and enable_thinking and not has_reasoning_item:
                think_fallback_buffer += buffer
            elif not is_thinking_tag:
                saved_content += buffer
                await queue.put({"event": "message", "data": {"delta": buffer}})

        if think_fallback_buffer and enable_thinking and not has_reasoning_item:
            await queue.put({"event": "model_thinking", "data": {"delta": think_fallback_buffer}})

        # 5. Save to DB
        ai_msg = db.query(Message).filter(Message.id == ai_msg_id).first()
        if ai_msg:
            ai_msg.content = saved_content if saved_content else "[No response]"
            db.commit()
            chat_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            chat_session.update_time = datetime.now(timezone.utc)
            chat_session.last_message_time = datetime.now(timezone.utc)
            if chat_session.memory_generated != 0:
                chat_session.memory_generated = 0
                chat_session.memory_error = None
            db.commit()

        usage["completion_tokens"] = len(full_ai_content)
        await queue.put({
            "event": "done",
            "data": {
                "finish_reason": finish_reason,
                "usage": usage,
                "message_id": ai_msg_id
            }
        })

    except Exception as e:
        logger.error(f"[GenTask] Error: {e}", exc_info=True)
        await queue.put({"event": "error", "data": {"code": "task_error", "detail": str(e)}})
    finally:
        await queue.put(None)
        db.close()

async def send_message_stream(db: Session, session_id: int, message_in: chat_schemas.MessageCreate):
    """
    Send a message and stream the LLM response.
    The actual generation is handled in a background task to ensure persistence.
    """
    db_session = get_session(db, session_id)
    if not db_session:
        yield {"event": "error", "data": {"code": "session_not_found", "detail": "Session not found"}}
        return

    llm_config = llm_service.get_active_config(db)
    if not llm_config:
        yield {"event": "error", "data": {"code": "config_not_found", "detail": "LLM configuration not found"}}
        return
    model_name = llm_config.model_name
    force_thinking = provider_rules.is_gemini_model(llm_config, model_name)
    effective_enable_thinking = message_in.enable_thinking and (
        bool(llm_config.capability_reasoning) or force_thinking
    )

    # 1. Save User Message
    user_msg = Message(session_id=session_id, role="user", content=message_in.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 2. Create AI Message Placeholder
    ai_msg = Message(session_id=session_id, role="assistant", content="", friend_id=db_session.friend_id)
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)

    # 3. Start Background Generation Task
    queue = asyncio.Queue()
    asyncio.create_task(_run_chat_generation_task(
        session_id=session_id,
        friend_id=db_session.friend_id,
        user_msg_id=user_msg.id,
        ai_msg_id=ai_msg.id,
        message_content=message_in.content,
        enable_thinking=effective_enable_thinking,
        queue=queue
    ))

    # 4. Stream events from the queue
    yield {
        "event": "start",
        "data": {
            "session_id": session_id,
            "message_id": ai_msg.id,
            "user_message_id": user_msg.id,
            "model": llm_config.model_name,
            "friend_id": db_session.friend_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    }

    while True:
        event = await queue.get()
        if event is None: # Sentinel
            break
        yield event


async def regenerate_message_stream(db: Session, session_id: int, ai_message_id: int):
    """
    Regenerate a specific AI message.
    1. Validate session and message.
    2. Soft delete the old AI message.
    3. Find the last user message as context.
    4. Trigger background generation.
    """
    db_session = get_session(db, session_id)
    if not db_session:
        yield {"event": "error", "data": {"code": "session_not_found", "detail": "Session not found"}}
        return

    # 1. Validate Session State
    if db_session.memory_generated != 0:
        yield {"event": "error", "data": {"code": "session_archived", "detail": "Session is archived"}}
        return

    # 2. Get and Validate Target Message
    old_ai_msg = db.query(Message).filter(Message.id == ai_message_id, Message.session_id == session_id).first()
    if not old_ai_msg:
        yield {"event": "error", "data": {"code": "message_not_found", "detail": "Message not found"}}
        return
    
    if old_ai_msg.role != "assistant":
        yield {"event": "error", "data": {"code": "invalid_role", "detail": "Can only regenerate assistant messages"}}
        return

    if old_ai_msg.deleted:
        yield {"event": "error", "data": {"code": "message_deleted", "detail": "Message already deleted"}}
        return

    # Ensure it's the last message (or at least no user messages after it)
    # Actually, for simplicity and safety, we only allow regenerating the very last message in the session.
    last_msg = db.query(Message).filter(Message.session_id == session_id, Message.deleted == False).order_by(Message.create_time.desc(), Message.id.desc()).first()
    if last_msg and last_msg.id != old_ai_msg.id:
        yield {"event": "error", "data": {"code": "not_latest", "detail": "Can only regenerate the latest message"}}
        return

    # 3. Soft Delete Old AI Message
    old_ai_msg.deleted = True
    db.commit()
    logger.info(f"[Regenerate] Soft deleted old AI message {old_ai_msg.id}")

    # 4. Find Last User Message (Context)
    last_user_msg = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.deleted == False, Message.role == "user")
        .order_by(Message.create_time.desc(), Message.id.desc())
        .first()
    )

    if not last_user_msg:
         yield {"event": "error", "data": {"code": "no_context", "detail": "No user message found to reply to"}}
         return

    llm_config = llm_service.get_active_config(db)
    if not llm_config:
        yield {"event": "error", "data": {"code": "config_not_found", "detail": "LLM configuration not found"}}
        return

    # 5. Create New AI Message Placeholder
    new_ai_msg = Message(session_id=session_id, role="assistant", content="", friend_id=db_session.friend_id)
    db.add(new_ai_msg)
    db.commit()
    db.refresh(new_ai_msg)

    # 6. Start Background Generation Task
    queue = asyncio.Queue()
    
    # Get thinking mode from global settings (frontend handles UI toggle state)
    enable_thinking = SettingsService.get_setting(db, "chat", "enable_thinking", False)
    model_name = llm_config.model_name
    force_thinking = provider_rules.is_gemini_model(llm_config, model_name)
    if enable_thinking and not llm_config.capability_reasoning and not force_thinking:
        enable_thinking = False

    asyncio.create_task(_run_chat_generation_task(
        session_id=session_id,
        friend_id=db_session.friend_id,
        user_msg_id=last_user_msg.id,
        ai_msg_id=new_ai_msg.id,
        message_content=last_user_msg.content, # Reuse last user content
        enable_thinking=enable_thinking, 
        queue=queue
    ))

    # 7. Stream events
    yield {
        "event": "start",
        "data": {
            "session_id": session_id,
            "message_id": new_ai_msg.id, # New ID
            "user_message_id": last_user_msg.id,
            "model": llm_config.model_name,
            "friend_id": db_session.friend_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    }

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event


def check_and_archive_expired_sessions(db: Session) -> int:
    """
    检查并归档所有过期的会话。
    用于后台定时任务。
    """
    from app.services.settings_service import SettingsService
    timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)
    
    # Calculate threshold time
    threshold_time = datetime.now(timezone.utc) - timedelta(seconds=timeout)
    
    # Query candidate sessions
    # memory_generated = False AND deleted = False AND last_message_time < threshold
    # 注意：last_message_time 为 NULL 的会话（新建但无消息）会被自动过滤，符合预期
    candidates = (
        db.query(ChatSession)
        .filter(
            ChatSession.memory_generated == 0,
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

async def process_memory_queue(db: Session):
    """
    处理全局记忆生成队列中的任务。
    由后台定时任务调用。
    """
    global _memory_generation_queue
    if not _memory_generation_queue:
        return
    
    # 拷贝当前队列并清空原队列
    batch = list(_memory_generation_queue)
    _memory_generation_queue.clear()
    
    logger.info(f"[Memory Worker] Processing {len(batch)} sessions from queue: {batch}")
    
    for session_id in batch:
        try:
            # 获取必要数据
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                continue
            
            friend = db.query(Friend).filter(Friend.id == session.friend_id).first()
            messages = (
                db.query(Message)
                .filter(Message.session_id == session_id, Message.deleted == False)
                .order_by(Message.create_time.asc())
                .all()
            )
            openai_messages = [{"role": m.role, "content": m.content} for m in messages]
            
            # 执行异步归档
            await _archive_session_async(
                session_id=session_id,
                openai_messages=openai_messages,
                friend_id=session.friend_id,
                friend_name=friend.name if friend else "Unknown"
            )
            logger.info(f"[Memory Worker] Session {session_id} processing completed.")
        except Exception as e:
            logger.error(f"[Memory Worker] Error processing session {session_id}: {str(e)}")
            # 失败后可以选择不再放回，由后续的过期检查兜底，或者放回
            # 这里我们不放回，因为若 _archive_session_async 报错通常是 SDK 问题，重试也可能失败

def recall_message(db: Session, message_id: int) -> bool:
    """
    Recall a user message.
    1. Check if session is active (not archived).
    2. Change message content to "你撤回了一条消息" and role to "system".
    3. If the next message is an assistant reply, soft delete it.
    """
    message = db.query(Message).filter(Message.id == message_id, Message.deleted == False).first()
    if not message:
        logger.warning(f"[Recall] Message {message_id} not found.")
        return False
        
    if message.role != 'user':
        logger.warning(f"[Recall] Cannot recall message {message_id} with role {message.role}.")
        return False

    session = db.query(ChatSession).filter(ChatSession.id == message.session_id).first()
    if not session:
        return False
        
    # Check if session is archived (memory_generated != 0)
    if session.memory_generated != 0:
        logger.warning(f"[Recall] Cannot recall message in archived session {session.id}.")
        return False
        
    # Logic:
    # 1. Update target message
    message.content = "你撤回了一条消息"
    message.role = "system"
    # Note: We do NOT soft delete the user message, we transform it.
    
    # 2. Find and delete subsequent assistant message
    # Get the next message in the same session (by time and ID)
    next_msg = (
        db.query(Message)
        .filter(
             Message.session_id == message.session_id,
             Message.deleted == False,
             (Message.create_time > message.create_time) | ((Message.create_time == message.create_time) & (Message.id > message.id))
        )
        .order_by(Message.create_time.asc(), Message.id.asc())
        .first()
    )
    
    if next_msg and next_msg.role == 'assistant':
        next_msg.deleted = True
        logger.info(f"[Recall] Cascading delete of assistant message {next_msg.id}")
        
    db.commit()
    logger.info(f"[Recall] Message {message_id} recalled successfully.")
    return True
