from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

# Type aliases
MemberType = Literal["user", "friend"]
MessageType = Literal["text", "system", "@"]

# --- Group Member Schemas ---
class GroupMemberBase(BaseModel):
    member_id: str
    member_type: MemberType

class GroupMemberCreate(GroupMemberBase):
    pass

class GroupMemberRead(GroupMemberBase):
    id: int
    group_id: int
    name: Optional[str] = None
    avatar: Optional[str] = None
    join_time: datetime

    class Config:
        from_attributes = True

# --- Group Message Schemas ---
class GroupMessageBase(BaseModel):
    content: str
    message_type: MessageType = "text"
    mentions: Optional[List[str]] = None

class GroupMessageCreate(GroupMessageBase):
    enable_thinking: bool = False


class GroupMessageRead(GroupMessageBase):
    id: int
    group_id: int
    session_id: int
    sender_id: str
    sender_type: MemberType
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True

# --- Group Schemas ---
class GroupBase(BaseModel):
    name: str
    avatar: Optional[str] = None
    description: Optional[str] = None

class GroupCreate(GroupBase):
    member_ids: List[str] # Initial members (usually friends)

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    description: Optional[str] = None

class GroupRead(GroupBase):
    id: int
    owner_id: str
    member_count: int = 0
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True

class GroupReadWithMembers(GroupRead):
    members: List[GroupMemberRead] = []

# --- Group Session Schemas ---
class GroupSessionRead(BaseModel):
    id: int
    group_id: int
    title: Optional[str] = None
    create_time: datetime
    update_time: datetime
    ended: bool
    last_message_time: Optional[datetime] = None

    class Config:
        from_attributes = True
