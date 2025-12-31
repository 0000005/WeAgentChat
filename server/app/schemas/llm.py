from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class LLMConfigBase(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = "gpt-3.5-turbo"

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
