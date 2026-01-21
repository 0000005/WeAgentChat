from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class EmbeddingSettingBase(BaseModel):
    config_name: Optional[str] = None
    embedding_provider: Optional[str] = "openai"
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_dim: Optional[int] = 1024
    embedding_model: Optional[str] = "BAAI/bge-m3"
    embedding_max_token_size: Optional[int] = 8000
    is_verified: Optional[bool] = False

class EmbeddingSettingCreate(EmbeddingSettingBase):
    pass

class EmbeddingSettingUpdate(EmbeddingSettingBase):
    embedding_provider: Optional[str] = None
    embedding_dim: Optional[int] = None
    embedding_model: Optional[str] = None
    embedding_max_token_size: Optional[int] = None

class EmbeddingSetting(EmbeddingSettingBase):
    id: int
    create_time: datetime
    update_time: datetime
    deleted: bool

    model_config = ConfigDict(from_attributes=True)
