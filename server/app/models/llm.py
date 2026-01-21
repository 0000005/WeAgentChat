from sqlalchemy import Column, Integer, String, Boolean
from datetime import datetime, timezone
from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, default="openai")
    config_name = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    model_name = Column(String, default="gpt-3.5-turbo")
    is_active = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    capability_vision = Column(Boolean, default=False)
    capability_search = Column(Boolean, default=False)
    capability_reasoning = Column(Boolean, default=False)
    capability_function_call = Column(Boolean, default=False)
    create_time = Column(UTCDateTime, default=utc_now)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now)
    deleted = Column(Boolean, default=False)
