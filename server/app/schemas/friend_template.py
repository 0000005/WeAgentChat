import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FriendTemplateBase(BaseModel):
    name: str = Field(..., max_length=64, description="模版名称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像 URL")
    description: str = Field(..., description="一句话简介")
    system_prompt: str = Field(..., description="完整人格设定")
    initial_message: Optional[str] = Field(None, description="初次对话开场白")
    tags: Optional[List[str]] = Field(None, description="标签列表")

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            # Try JSON first
            if value.startswith("["):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            # Split by comma (handles both "tag1,tag2" and "tag1, tag2")
            tags = [t.strip() for t in value.split(",") if t.strip()]
            return tags
        return None


class FriendTemplateCreate(FriendTemplateBase):
    pass


class FriendTemplate(FriendTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FriendTemplateCreateFriend(BaseModel):
    name: str = Field(..., max_length=64, description="好友名称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像 URL")
    description: str = Field(..., description="一句话简介")
    system_prompt: str = Field(..., description="完整人格设定")
    initial_message: Optional[str] = Field(None, description="初次对话开场白")
