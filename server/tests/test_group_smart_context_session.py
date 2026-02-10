from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.group import Group, GroupMember, GroupSession
from app.schemas import group as group_schemas
from app.services.group_chat_service import (
    group_chat_service,
    resolve_session_for_incoming_group_message,
)
from app.services.memo.constants import DEFAULT_USER_ID
from app.services.settings_service import SettingsService


def _create_group(db: Session, name: str) -> Group:
    group = Group(name=name, owner_id=DEFAULT_USER_ID)
    db.add(group)
    db.commit()
    db.refresh(group)

    db.add(
        GroupMember(
            group_id=group.id,
            member_id=DEFAULT_USER_ID,
            member_type="user",
        )
    )
    db.commit()
    return group


def _set_session_settings(db: Session, timeout: int = 1800, smart_enabled: bool = False):
    SettingsService.set_setting(db, "session", "passive_timeout", timeout, "int")
    SettingsService.set_setting(db, "session", "smart_context_enabled", smart_enabled, "bool")


@pytest.mark.asyncio
async def test_group_resolve_session_no_timeout_skips_llm_judgment(db: Session):
    group = _create_group(db, "group-smart-no-timeout")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = group_chat_service.create_group_session(db, group.id)
    session.last_message_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    with patch(
        "app.services.group_chat_service._judge_group_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_judge:
        resolved = await resolve_session_for_incoming_group_message(db, group.id, "继续聊")

    assert resolved.id == session.id
    mock_judge.assert_not_called()


@pytest.mark.asyncio
async def test_group_resolve_session_timeout_with_switch_off_creates_new(db: Session):
    group = _create_group(db, "group-smart-off")
    _set_session_settings(db, timeout=1800, smart_enabled=False)
    session = group_chat_service.create_group_session(db, group.id)
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    resolved = await resolve_session_for_incoming_group_message(db, group.id, "新消息")

    db.refresh(session)
    assert resolved.id != session.id
    assert session.ended is True
    assert resolved.ended is False


@pytest.mark.asyncio
async def test_group_resolve_session_timeout_related_reuses_old_session(db: Session):
    group = _create_group(db, "group-smart-related")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = group_chat_service.create_group_session(db, group.id)
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    with patch(
        "app.services.group_chat_service._judge_group_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resolved = await resolve_session_for_incoming_group_message(db, group.id, "接着上个话题")

    db.refresh(session)
    assert resolved.id == session.id
    assert session.ended is False


@pytest.mark.asyncio
async def test_group_resolve_session_timeout_unrelated_creates_new(db: Session):
    group = _create_group(db, "group-smart-unrelated")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    session = group_chat_service.create_group_session(db, group.id)
    session.last_message_time = datetime.now(timezone.utc) - timedelta(hours=2)
    db.commit()

    with patch(
        "app.services.group_chat_service._judge_group_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resolved = await resolve_session_for_incoming_group_message(db, group.id, "完全新话题")

    db.refresh(session)
    assert resolved.id != session.id
    assert session.ended is True
    assert resolved.ended is False


@pytest.mark.asyncio
async def test_group_resolve_archived_session_can_be_resurrected_by_judgment(db: Session):
    group = _create_group(db, "group-smart-archived")
    _set_session_settings(db, timeout=1800, smart_enabled=True)
    archived = group_chat_service.create_group_session(db, group.id)
    archived.ended = True
    archived.last_message_time = datetime.now(timezone.utc) - timedelta(days=3)
    db.commit()

    with patch(
        "app.services.group_chat_service._judge_group_smart_context_relevance",
        new_callable=AsyncMock,
        return_value=True,
    ):
        resolved = await resolve_session_for_incoming_group_message(db, group.id, "继续之前讨论")

    db.refresh(archived)
    assert resolved.id == archived.id
    assert archived.ended is False


@pytest.mark.asyncio
async def test_send_group_message_force_new_session_skips_judgment(db: Session):
    group = _create_group(db, "group-smart-force-new")
    old_session = group_chat_service.create_group_session(db, group.id)
    old_session.last_message_time = datetime.now(timezone.utc)
    db.commit()

    async def _fake_stream_with_session(
        db: Session,
        group_id: int,
        session: GroupSession,
        message_in: group_schemas.GroupMessageCreate,
        sender_id: str = DEFAULT_USER_ID,
    ):
        yield {
            "event": "start",
            "data": {
                "group_id": group_id,
                "session_id": session.id,
                "sender_id": sender_id,
            },
        }
        yield {"event": "done", "data": {"session_id": session.id}}

    with patch(
        "app.services.group_chat_service.resolve_session_for_incoming_group_message",
        new_callable=AsyncMock,
    ) as mock_resolve, patch(
        "app.services.group_chat_service.GroupChatService._send_group_message_stream_with_session",
        new=_fake_stream_with_session,
    ):
        events = []
        async for evt in group_chat_service.send_group_message_stream(
            db,
            group_id=group.id,
            message_in=group_schemas.GroupMessageCreate(content="hello"),
            force_new_session=True,
        ):
            events.append(evt)

    active_sessions = (
        db.query(GroupSession)
        .filter(
            GroupSession.group_id == group.id,
            GroupSession.session_type == "normal",
            GroupSession.ended == False,
        )
        .all()
    )
    db.refresh(old_session)
    assert len(active_sessions) == 1
    assert events[0]["event"] == "start"
    assert events[0]["data"]["session_id"] == active_sessions[0].id
    assert events[0]["data"]["session_id"] == old_session.id
    assert old_session.ended is False
    mock_resolve.assert_not_called()
