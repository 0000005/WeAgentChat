from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator

# --- Message Schemas ---
class MessageBase(BaseModel):
    role: str
    content: str
    friend_id: Optional[int] = None
    voice_payload: Optional[Dict[str, Any]] = None

class MessageCreate(BaseModel):
    content: str
    enable_thinking: bool = False  # 是否启用思考模式

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

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
    memory_generated: int = 0
    memory_error: Optional[str] = None
    last_message_time: Optional[datetime] = None

    class Config:
        from_attributes = True

class ChatSessionReadWithStats(ChatSessionRead):
    message_count: int = 0
    last_message_preview: Optional[str] = None
    is_active: bool = False


class PageContextPayload(BaseModel):
    supported: bool = False
    reason: Optional[str] = None
    text: Optional[str] = None
    excerpt: Optional[str] = None
    locator: Optional[str] = None
    toc_path: List[str] = Field(default_factory=list, alias="tocPath")
    truncated: bool = False
    source_type: Optional[str] = Field(None, alias="sourceType")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("reason", "text", "excerpt", "locator", "source_type", mode="before")
    @classmethod
    def normalize_optional_text_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SelectedQuotePayload(BaseModel):
    text: str = Field(..., min_length=0, max_length=4000)
    excerpt: Optional[str] = None
    locator: Optional[str] = None
    toc_path: List[str] = Field(default_factory=list, alias="tocPath")
    truncated: bool = False
    source_type: Optional[str] = Field(None, alias="sourceType")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text_field(cls, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("excerpt", "locator", "source_type", mode="before")
    @classmethod
    def normalize_text_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class BookReadingMessageCreate(BaseModel):
    user_message: str = Field(..., min_length=1, max_length=8000)
    book_id: int
    friend_id: int
    page_context: Optional[PageContextPayload] = None
    selected_quote: Optional[SelectedQuotePayload] = None
    enable_thinking: bool = False

    @field_validator("user_message", mode="before")
    @classmethod
    def normalize_user_message(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value



