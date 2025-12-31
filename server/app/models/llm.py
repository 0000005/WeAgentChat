from sqlalchemy import Column, Integer, String, DateTime, Boolean, func
from app.db.base import Base

class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    base_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    model_name = Column(String, default="gpt-3.5-turbo")
    create_time = Column(DateTime, default=func.now())
    update_time = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(Boolean, default=False)
