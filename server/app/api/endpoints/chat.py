import json
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas import chat as chat_schemas
from app.services import chat_service

router = APIRouter()

@router.get("/sessions", response_model=List[chat_schemas.ChatSessionRead])
def read_sessions(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Get all chat sessions.
    """
    sessions = chat_service.get_sessions(db, skip=skip, limit=limit)
    return sessions

@router.post("/sessions", response_model=chat_schemas.ChatSessionRead)
def create_session(
    *,
    db: Session = Depends(deps.get_db),
    session_in: chat_schemas.ChatSessionCreate,
):
    """
    Create a new chat session.
    """
    session = chat_service.create_session(db, session_in=session_in)
    return session

@router.patch("/sessions/{session_id}", response_model=chat_schemas.ChatSessionRead)
def update_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    session_in: chat_schemas.ChatSessionUpdate,
):
    """
    Update a chat session (e.g. title).
    """
    session = chat_service.update_session(db, session_id=session_id, session_in=session_in)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/sessions/{session_id}")
def delete_session(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
):
    """
    Soft delete a chat session.
    """
    success = chat_service.delete_session(db, session_id=session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}

@router.get("/sessions/{session_id}/messages", response_model=List[chat_schemas.MessageRead])
def read_messages(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    skip: int = 0,
    limit: int = 100,
):
    """
    Get messages for a specific session.
    """
    # Verify session exists first
    session = chat_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = chat_service.get_messages(db, session_id=session_id, skip=skip, limit=limit)
    return messages

@router.post("/sessions/{session_id}/messages")
async def send_message(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    message_in: chat_schemas.MessageCreate,
):
    """
    Send a message to a session and get the AI response via SSE.
    """
    async def event_generator():
        async for event_data in chat_service.send_message_stream(db, session_id=session_id, message_in=message_in):
            # event_data is a dict with 'event' and 'data' keys
            event_type = event_data.get("event", "message")
            data_payload = event_data.get("data", {})
            
            # Serialize data to JSON
            json_data = json.dumps(data_payload, ensure_ascii=False)
            
            yield f"event: {event_type}\ndata: {json_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Friend-centric APIs (WeChat-style) ---

@router.get("/friends/{friend_id}/messages", response_model=List[chat_schemas.MessageRead])
def read_friend_messages(
    *,
    db: Session = Depends(deps.get_db),
    friend_id: int,
    skip: int = 0,
    limit: int = 200,
):
    """
    Get all messages for a specific friend across all sessions.
    This provides a WeChat-style merged chat history view.
    """
    messages = chat_service.get_messages_by_friend(db, friend_id=friend_id, skip=skip, limit=limit)
    return messages

@router.post("/friends/{friend_id}/messages")
async def send_message_to_friend(
    *,
    db: Session = Depends(deps.get_db),
    friend_id: int,
    message_in: chat_schemas.MessageCreate,
):
    """
    Send a message to a friend. This will find or create an appropriate session.
    """
    # Get or create a session for this friend
    session = chat_service.get_or_create_session_for_friend(db, friend_id=friend_id)
    
    async def event_generator():
        async for event_data in chat_service.send_message_stream(db, session_id=session.id, message_in=message_in):
            event_type = event_data.get("event", "message")
            data_payload = event_data.get("data", {})
            json_data = json.dumps(data_payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {json_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
