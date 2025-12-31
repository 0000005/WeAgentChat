from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.chat import ChatSession, Message
from app.models.persona import Persona
from app.models.llm import LLMConfig
from app.schemas import chat as chat_schemas
from datetime import datetime

from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, set_default_openai_client, set_default_openai_api

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
    Send a message (User) and stream the LLM response.
    """
    # 1. Verify session and fetch persona/config
    db_session = get_session(db, session_id)
    if not db_session:
        yield "error: Session not found"
        return

    persona = db.query(Persona).filter(Persona.id == db_session.persona_id).first()
    system_prompt = persona.system_prompt if persona else "你是一名通用问答型 AI 助手。"

    llm_config = db.query(LLMConfig).filter(LLMConfig.deleted == False).order_by(LLMConfig.id.desc()).first()
    if not llm_config:
        yield "error: LLM configuration not found"
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

    result = Runner.run_streamed(agent, agent_messages)
    
    # We yield the ID of the user message first or just start with content deltas
    # For SSE, we will yield text chunks
    
    full_ai_content = ""
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            delta = event.data.delta
            if delta:
                full_ai_content += delta
                yield delta

    # 5. Save AI Response once finished
    if full_ai_content:
        ai_msg = Message(
            session_id=session_id,
            role="assistant",
            content=full_ai_content,
            persona_id=db_session.persona_id
        )
        db.add(ai_msg)
        db_session.update_time = datetime.now()
        db.commit()
        db.refresh(ai_msg)