from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class FriendBase(BaseModel):
    name: str = Field(..., max_length=64, description="好友名称")
    description: Optional[str] = Field(None, max_length=255, description="好友描述")
    system_prompt: Optional[str] = None
    is_preset: bool = Field(False, description="是否为系统预设")
    avatar: Optional[str] = Field(None, description="头像URL")
    script_expression: bool = Field(True, description="是否启用剧本式表达")

class FriendCreate(FriendBase):
    pass

class FriendUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=255)
    system_prompt: Optional[str] = None
    is_preset: Optional[bool] = None
    avatar: Optional[str] = Field(None, description="头像URL")
    script_expression: Optional[bool] = Field(None, description="是否启用剧本式表达")
    pinned_at: Optional[datetime] = None  # Direct update of pinned_at

class Friend(FriendBase):
    id: int
    create_time: datetime
    update_time: datetime
    pinned_at: Optional[datetime] = None
    deleted: bool
    last_message: Optional[str] = None
    last_message_role: Optional[str] = None
    last_message_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
