from sqlalchemy.orm import Session
from typing import List, Optional
import re
from app.models.chat import ChatSession, Message
from app.models.persona import Persona
from app.models.llm import LLMConfig
from app.schemas import chat as chat_schemas
from datetime import datetime

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
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
    """
    db_session = ChatSession(
        persona_id=session_in.persona_id,
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

async def send_message(db: Session, session_id: int, message_in: chat_schemas.MessageCreate) -> Message:
    """
    Send a message (User) and get a real LLM response using openai-agents.
    """
    # 1. Verify session and fetch persona/config
    db_session = get_session(db, session_id)
    if not db_session:
        return None

    persona = db.query(Persona).filter(Persona.id == db_session.persona_id).first()
    system_prompt = persona.system_prompt if persona else "你是一名通用问答型 AI 助手。"

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
        name=persona.name if persona else "AI",
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
        persona_id=db_session.persona_id
    )
    db.add(ai_msg)
    
    # Update session update_time
    db_session.update_time = datetime.now()
    
    db.commit()
    db.refresh(ai_msg)

    return ai_msg

async def send_message_stream(db: Session, session_id: int, message_in: chat_schemas.MessageCreate):
    """
    Send a message (User) and stream the LLM response using SSE event structure.
    Yields dictionaries representing SSE events.
    """
    # 1. Verify session and fetch persona/config
    db_session = get_session(db, session_id)
    if not db_session:
        yield {"event": "error", "data": {"code": "session_not_found", "detail": "Session not found"}}
        return

    persona = db.query(Persona).filter(Persona.id == db_session.persona_id).first()
    system_prompt = persona.system_prompt if persona else "你是一名通用问答型 AI 助手。"
    persona_name = persona.name if persona else "AI"

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
        persona_id=db_session.persona_id
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
            "persona_id": db_session.persona_id,
            "persona_name": persona_name,
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
        name=persona_name,
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

    try:
        result = Runner.run_streamed(agent, agent_messages)
        
        async for event in result.stream_events():
            # Handle reasoning item events (from models with native reasoning support)
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
    db_session.update_time = datetime.now()
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