from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class LLMConfigBase(BaseModel):
    provider: Optional[str] = "openai"
    config_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = "gpt-3.5-turbo"
    is_active: Optional[bool] = False
    is_verified: Optional[bool] = False
    capability_vision: Optional[bool] = False
    capability_search: Optional[bool] = False
    capability_reasoning: Optional[bool] = False
    capability_function_call: Optional[bool] = False

class LLMConfigCreate(LLMConfigBase):
    pass

class LLMConfigUpdate(LLMConfigBase):
    pass

class LLMConfig(LLMConfigBase):
    id: int
    create_time: datetime
    update_time: datetime
    deleted: bool

    model_config = ConfigDict(from_attributes=True)


class LLMConfigRead(LLMConfigBase):
    id: Optional[int] = None
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    deleted: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)
