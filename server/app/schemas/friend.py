from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List

class FriendBase(BaseModel):
    name: str = Field(..., max_length=64, description="好友名称")
    description: Optional[str] = Field(None, max_length=1024, description="好友描述")
    system_prompt: Optional[str] = None
    is_preset: bool = Field(False, description="是否为系统预设")
    avatar: Optional[str] = Field(None, description="头像URL")
    script_expression: bool = Field(False, description="是否启用剧本式表达")
    temperature: float = Field(1.0, ge=0.0, le=2.0, description="温度参数")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-P 参数")

class FriendCreate(FriendBase):
    pass

class FriendUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=1024)
    system_prompt: Optional[str] = None
    is_preset: Optional[bool] = None
    avatar: Optional[str] = Field(None, description="头像URL")
    script_expression: Optional[bool] = Field(None, description="是否启用剧本式表达")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
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

class FriendRecommendationRequest(BaseModel):
    topic: str = Field(..., description="用户想要讨论的话题")
    exclude_names: List[str] = Field(default_factory=list, description="需要排除的人物名称列表")

class FriendRecommendationItem(BaseModel):
    name: str = Field(..., description="推荐的好友名称")
    reason: str = Field(..., description="推荐理由")
    description_hint: str = Field(..., description="用于生成设定的背景描述建议")

class FriendRecommendationResponse(BaseModel):
    recommendations: List[FriendRecommendationItem]
