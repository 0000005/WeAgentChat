from sqlalchemy import Column, Integer, String, Text
from app.db.base import Base
from app.db.types import UTCDateTime, utc_now

class VoiceTimbre(Base):
    __tablename__ = "voice_timbres"

    id = Column(Integer, primary_key=True, index=True)
    voice_id = Column(String(64), unique=True, index=True, nullable=False) # e.g., "Cherry"
    name = Column(String(64), nullable=False) # e.g., "芊悦"
    description = Column(Text, nullable=True)
    gender = Column(String(20), nullable=True) # "male", "female", "other"
    preview_url = Column(String(512), nullable=True)
    supported_models = Column(Text, nullable=True) # comma-separated model names
    category = Column(String(64), nullable=True) # e.g., "Standard", "Special"
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
