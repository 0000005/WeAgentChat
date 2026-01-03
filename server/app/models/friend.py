from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.db.base import Base

class Friend(Base):
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    is_preset = Column(Boolean, default=False, nullable=False)
    create_time = Column(DateTime, default=func.now(), nullable=False)
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)
