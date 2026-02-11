from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class VoiceTimbreOut(BaseModel):
    id: int
    voice_id: str
    name: str
    description: Optional[str] = None
    gender: Optional[str] = None
    preview_url: Optional[str] = None
    supported_models: List[str] = []
    category: Optional[str] = None
    create_time: datetime

    @field_validator("supported_models", mode="before")
    @classmethod
    def parse_supported_models(cls, v):
        """将逗号分隔的字符串转为列表"""
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        if v is None:
            return []
        return v

    class Config:
        from_attributes = True


class VoiceTestRequest(BaseModel):
    api_key: str = Field(..., min_length=1)
    model: str = "qwen3-tts-instruct-flash"
    voice_id: str = Field(..., min_length=1)
    text: Optional[str] = None
    base_url: Optional[str] = None


class VoiceTestResponse(BaseModel):
    success: bool
    message: str
    model: str
    voice_id: str
    audio_url: str
