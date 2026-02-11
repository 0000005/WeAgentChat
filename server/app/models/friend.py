from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, Float
from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class Friend(Base):
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    description = Column(String(255), nullable=True)
    system_prompt = Column(Text, nullable=True)
    is_preset = Column(Boolean, default=False, nullable=False)
    avatar = Column(String(255), nullable=True)
    script_expression = Column(Boolean, default=False, nullable=False)
    temperature = Column(Float, default=1.0, nullable=False)
    top_p = Column(Float, default=0.9, nullable=False)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)
    pinned_at = Column(UTCDateTime, nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)

