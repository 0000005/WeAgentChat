from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    avatar = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    owner_id = Column(String(64), nullable=False)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("GroupMessage", back_populates="group", cascade="all, delete-orphan")
    sessions = relationship("GroupSession", back_populates="group", cascade="all, delete-orphan")


class GroupSession(Base):
    __tablename__ = "group_sessions"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    title = Column(String(128), default="群聊会话", nullable=True)
    session_type = Column(String(20), default="normal", nullable=False)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)
    ended = Column(Boolean, default=False, nullable=False)
    last_message_time = Column(UTCDateTime, nullable=True)

    group = relationship("Group", back_populates="sessions")
    messages = relationship("GroupMessage", back_populates="session", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    member_id = Column(String(64), nullable=False) # Can be user UUID or friend ID as string
    member_type = Column(String(20), nullable=False) # 'user' or 'friend'
    join_time = Column(UTCDateTime, default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint('group_id', 'member_id', name='uq_group_member'),
    )

    # Relationships
    group = relationship("Group", back_populates="members")


class GroupMessage(Base):
    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("group_sessions.id"), nullable=False)
    sender_id = Column(String(64), nullable=False)
    sender_type = Column(String(20), nullable=False) # 'user' or 'friend'
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text", nullable=False) # 'text', 'system', '@'
    mentions = Column(JSON, nullable=True) # List of member IDs
    debate_side = Column(String(20), nullable=True) # 'affirmative' / 'negative'
    voice_payload = Column(JSON, nullable=True)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index('ix_group_messages_group_id_create_time', 'group_id', 'create_time'),
    )

    # Relationships
    group = relationship("Group", back_populates="messages")
    session = relationship("GroupSession", back_populates="messages")

    @property
    def session_type(self):
        return self.session.session_type if self.session else None


class GroupAutoDriveRun(Base):
    __tablename__ = "group_auto_drive_runs"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("group_sessions.id"), nullable=False)
    mode = Column(String(20), nullable=False)
    topic_json = Column(JSON, nullable=False)
    roles_json = Column(JSON, nullable=False)
    turn_limit = Column(Integer, nullable=False)
    end_action = Column(String(20), nullable=False)
    judge_id = Column(String(64), nullable=True)
    summary_by = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="running")
    phase = Column(String(32), nullable=True)
    current_round = Column(Integer, nullable=False, default=0)
    current_turn = Column(Integer, nullable=False, default=0)
    next_speaker_id = Column(String(64), nullable=True)
    pause_reason = Column(String(128), nullable=True)
    started_at = Column(UTCDateTime, default=utc_now, nullable=False)
    ended_at = Column(UTCDateTime, nullable=True)
    create_time = Column(UTCDateTime, default=utc_now, nullable=False)
    update_time = Column(UTCDateTime, default=utc_now, onupdate=utc_now, nullable=False)

    group = relationship("Group", foreign_keys=[group_id])
    session = relationship("GroupSession", foreign_keys=[session_id])
