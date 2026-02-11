from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    friend_id = Column(Integer, ForeignKey("friends.id"), nullable=False)
    title = Column(String(128), default="新对话", nullable=True)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)
    # 记忆生成状态:
    # 0 = 未生成 (活跃会话)
    # 1 = 已生成 (成功归档)
    # 2 = 生成失败 (SDK错误/配置缺失等)
    # 3 = 生成中 (正在归档处理)
    memory_generated = Column(Integer, default=0, nullable=False)
    # 生成失败原因
    memory_error = Column(Text, nullable=True)
    # 最后一条消息的时间
    last_message_time = Column(UTCDateTime, nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    # friend = relationship("Friend") # Optional, if needed


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("friends.id"), nullable=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    voice_payload = Column(JSON, nullable=True)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")


