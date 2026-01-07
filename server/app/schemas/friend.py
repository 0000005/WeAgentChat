from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

class FriendBase(BaseModel):
    name: str = Field(..., max_length=64, description="好友名称")
    description: Optional[str] = Field(None, max_length=255, description="好友描述")
    system_prompt: Optional[str] = Field(None, description="系统提示词")
    is_preset: bool = Field(False, description="是否为系统预设")

class FriendCreate(FriendBase):
    pass

class FriendUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=255)
    system_prompt: Optional[str] = None
    is_preset: Optional[bool] = None
    pinned_at: Optional[datetime] = None  # Direct update of pinned_at

class Friend(FriendBase):
    id: int
    create_time: datetime
    update_time: datetime
    pinned_at: Optional[datetime] = None
    deleted: bool

    model_config = ConfigDict(from_attributes=True)
