from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

# --- Message Schemas ---
class MessageBase(BaseModel):
    role: str
    content: str
    friend_id: Optional[int] = None

class MessageCreate(BaseModel):
    content: str
    enable_thinking: bool = False  # 是否启用思考模式

class MessageRead(MessageBase):
    id: int
    session_id: int
    create_time: datetime
    update_time: datetime
    deleted: bool

    class Config:
        from_attributes = True

# --- ChatSession Schemas ---
class ChatSessionBase(BaseModel):
    title: Optional[str] = "新对话"
    friend_id: int

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None

class ChatSessionRead(ChatSessionBase):
    id: int
    create_time: datetime
    update_time: datetime
    deleted: bool
    
    # Optional: include messages if needed in list/detail view
    # messages: List[MessageRead] = []

    class Config:
        from_attributes = True
