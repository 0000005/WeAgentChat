from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.chat import ChatSession, Message
from app.models.friend import Friend
from app.models.llm import LLMConfig
from app.schemas.chat import ChatSessionCreate, MessageCreate
from app.services import chat_service
from app.services.chat_service import (
    check_and_archive_expired_sessions,
    create_session,
    resolve_session_for_incoming_friend_message,
)
from app.services.settings_service import SettingsService


def _create_friend(db: Session, name: str) -> Friend:
    friend = Friend(name=name, system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)
    return friend


def _set_session_settings(db: Session, timeout: int = 1800, smart_enabled: bool = False):
    SettingsService.set_setting(db, "session", "passive_timeout", timeout, "int")
    SettingsService.set_setting(db, "session", "smart_context_enabled", smart_enabled, "bool")


@pytest.mark.asyncio
async def test_resolve_session_no_timeout_skips_llm_judgment(db: Session):
    friend = _create_friend(db, "smart-context-no-timeout")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="s1"))
    session.last_message_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_judge:
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续刚才的话题")

    assert resolved.id == session.id
    mock_judge.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_session_timeout_with_switch_off_creates_new(db: Session):
    friend = _create_friend(db, "smart-context-off")
    _set_session_settings(db, timeout=1800, smart_enabled=False)
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "新消息")

    db.refresh(session)
    assert resolved.id != session.id
    assert session.memory_generated != 0
    assert resolved.memory_generated == 0


@pytest.mark.asyncio
async def test_resolve_session_timeout_related_reuses_old_session(db: Session):
    friend = _create_friend(db, "smart-context-related")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "接着上一个问题")

    db.refresh(session)
    assert resolved.id == session.id
    assert session.memory_generated == 0


@pytest.mark.asyncio
async def test_resolve_session_timeout_unrelated_creates_new(db: Session):
    friend = _create_friend(db, "smart-context-unrelated")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "今天天气不错")

    db.refresh(session)
    assert resolved.id != session.id
    assert session.memory_generated != 0


@pytest.mark.asyncio
async def test_resolve_session_related_rolls_back_archived_state(db: Session):
    friend = _create_friend(db, "smart-context-rollback")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    async def _mark_archived_then_related(_db: Session, _session: ChatSession, _msg: str):
        _session.memory_generated = 1
        _db.commit()
        return True

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        side_effect=_mark_archived_then_related,
    ), patch(
        "app.services.chat_service._schedule_session_memory_deletion",
    ) as mock_schedule:
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续")

    db.refresh(session)
    assert resolved.id == session.id
    assert session.memory_generated == 0
    mock_schedule.assert_called_once_with(session.id)


@pytest.mark.asyncio
async def test_resolve_archived_session_can_be_resurrected_by_judgment(db: Session):
    friend = _create_friend(db, "smart-context-archived-resurrect")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    archived = create_session(db, ChatSessionCreate(friend_id=friend.id, title="archived"))
    archived.memory_generated = 1
    archived.last_message_time = datetime.now(timezone.utc) - timedelta(days=3)
    db.commit()

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.chat_service._schedule_session_memory_deletion",
    ) as mock_schedule:
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续之前的话题")

    db.refresh(archived)
    assert resolved.id == archived.id
    assert archived.memory_generated == 0
    mock_schedule.assert_called_once_with(archived.id)


@pytest.mark.asyncio
async def test_resolve_archived_session_within_timeout_resurrects_without_judgment(db: Session):
    friend = _create_friend(db, "smart-context-archived-within-timeout")
    _set_session_settings(db, timeout=1800, smart_enabled=False)
    archived = create_session(db, ChatSessionCreate(friend_id=friend.id, title="archived"))
    archived.memory_generated = 1
    archived.last_message_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_judge, patch(
        "app.services.chat_service._schedule_session_memory_deletion",
    ) as mock_schedule:
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续")

    db.refresh(archived)
    assert resolved.id == archived.id
    assert archived.memory_generated == 0
    mock_judge.assert_not_called()
    mock_schedule.assert_called_once_with(archived.id)


@pytest.mark.asyncio
async def test_resolve_archived_session_with_smart_off_creates_new(db: Session):
    friend = _create_friend(db, "smart-context-archived-off")
    _set_session_settings(db, timeout=1800, smart_enabled=False)
    archived = create_session(db, ChatSessionCreate(friend_id=friend.id, title="archived"))
    archived.memory_generated = 1
    db.commit()

    resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续")

    db.refresh(archived)
    assert resolved.id != archived.id
    assert archived.memory_generated == 1


@pytest.mark.asyncio
async def test_empty_active_within_timeout_uses_judgment_when_smart_enabled(db: Session):
    friend = _create_friend(db, "smart-context-empty-active-override")
    _set_session_settings(db, timeout=1800, smart_enabled=True)

    archived = create_session(db, ChatSessionCreate(friend_id=friend.id, title="archived"))
    archived.memory_generated = 1
    archived.last_message_time = datetime.now(timezone.utc) - timedelta(minutes=8)
    db.commit()

    empty_active = create_session(db, ChatSessionCreate(friend_id=friend.id, title="empty-active"))

    with patch(
        "app.services.chat_service._judge_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_judge, patch(
        "app.services.chat_service._schedule_session_memory_deletion",
    ) as mock_schedule:
        resolved = await resolve_session_for_incoming_friend_message(db, friend.id, "继续")

    db.refresh(archived)
    assert resolved.id == empty_active.id
    assert archived.memory_generated == 1
    mock_judge.assert_called_once()
    mock_schedule.assert_not_called()


def test_background_archiver_uses_hard_timeout(db: Session):
    friend = _create_friend(db, "smart-context-hard-timeout")

    recent = ChatSession(friend_id=friend.id, title="recent")
    recent.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    expired = ChatSession(friend_id=friend.id, title="expired")
    expired.last_message_time = datetime.now(timezone.utc) - timedelta(hours=25)
    db.add(recent)
    db.add(expired)
    db.commit()
    db.refresh(recent)
    db.refresh(expired)

    archived_count = check_and_archive_expired_sessions(db)

    db.refresh(recent)
    db.refresh(expired)
    assert archived_count >= 1
    assert recent.memory_generated == 0
    assert expired.memory_generated != 0


@pytest.mark.asyncio
async def test_smart_context_judge_fallback_on_llm_error(db: Session):
    friend = _create_friend(db, "smart-context-judge-fallback")
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))

    llm_config = LLMConfig(
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
        model_name="gpt-4o-mini",
        capability_function_call=True,
    )
    db.add(llm_config)
    db.commit()
    db.refresh(llm_config)

    SettingsService.set_setting(db, "session", "smart_context_model", "", "string")
    SettingsService.set_setting(db, "chat", "active_llm_config_id", llm_config.id, "int")

    with patch("app.services.chat_service.Runner.run", side_effect=Exception("llm error")):
        related = await chat_service._judge_smart_context_relevance(db, session, "继续")

    assert related is False


@pytest.mark.asyncio
async def test_send_message_to_friend_force_new_session_skips_judgment(db: Session):
    friend = _create_friend(db, "smart-context-force-new")
    old_session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="old"))
    db.add(Message(session_id=old_session.id, role="user", content="old"))
    db.commit()

    async def _fake_stream(_db: Session, session_id: int, message_in: MessageCreate):
        yield {"event": "start", "data": {"session_id": session_id, "content": message_in.content}}
        yield {"event": "done", "data": {"message_id": 1}}

    with patch(
        "app.services.chat_service.resolve_session_for_incoming_friend_message",
        new_callable=AsyncMock,
    ) as mock_resolve, patch(
        "app.services.chat_service.send_message_stream",
        side_effect=_fake_stream,
    ):
        events = []
        async for evt in chat_service.send_message_to_friend_stream(
            db,
            friend_id=friend.id,
            message_in=MessageCreate(content="hello"),
            force_new_session=True,
        ):
            events.append(evt)

    active_sessions = (
        db.query(ChatSession)
        .filter(
            ChatSession.friend_id == friend.id,
            ChatSession.deleted == False,
            ChatSession.memory_generated == 0,
        )
        .all()
    )
    db.refresh(old_session)
    assert len(active_sessions) == 1
    assert events[0]["event"] == "start"
    assert events[0]["data"]["session_id"] == max(s.id for s in active_sessions)
    assert events[0]["data"]["session_id"] != old_session.id
    assert old_session.memory_generated != 0
    mock_resolve.assert_not_called()
