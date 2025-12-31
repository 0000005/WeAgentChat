from fastapi import APIRouter, Depends, HTTPException, Body
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

@router.post("/sessions/{session_id}/messages", response_model=chat_schemas.MessageRead)
async def send_message(
    *,
    db: Session = Depends(deps.get_db),
    session_id: int,
    message_in: chat_schemas.MessageCreate,
):
    """
    Send a message to a session and get the AI response.
    """
    message = await chat_service.send_message(db, session_id=session_id, message_in=message_in)
    if not message:
        raise HTTPException(status_code=404, detail="Session not found")
    return message
