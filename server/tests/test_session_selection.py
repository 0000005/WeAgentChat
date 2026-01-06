import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.services.chat_service import (
    get_or_create_session_for_friend,
    create_session,
    archive_session,
)
from app.models.chat import ChatSession, Message
from app.models.friend import Friend
from app.schemas.chat import ChatSessionCreate


def test_get_or_create_returns_latest_session(db: Session):
    """测试: get_or_create_session_for_friend 应该返回最新创建的会话（ID最大）"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建三个会话，ID 会依次为 1, 2, 3
    session_1 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 1"))
    session_2 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 2"))
    session_3 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 3"))

    # 3. Action: 获取活跃会话
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 4. Assert: 应该返回最新的会话（ID 最大）
    assert active_session.id == session_3.id
    assert active_session.title == "Session 3"


def test_get_or_create_skips_archived_sessions(db: Session):
    """测试: 已归档的会话（memory_generated=True）不应被误选"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建两个会话
    session_old = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Old Session"))
    session_new = create_session(db, ChatSessionCreate(friend_id=friend.id, title="New Session"))

    # 3. 给旧会话添加一些消息
    m1 = Message(session_id=session_old.id, role="user", content="Hello")
    m2 = Message(session_id=session_old.id, role="assistant", content="Hi there")
    db.add(m1)
    db.add(m2)
    db.commit()

    # 4. 归档旧会话
    archive_session(db, session_old.id)
    db.refresh(session_old)
    assert session_old.memory_generated is True

    # 5. Action: 获取活跃会话
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 6. Assert: 应该返回新的会话，而不是已归档的旧会话
    assert active_session.id == session_new.id
    assert active_session.title == "New Session"


def test_get_or_create_creates_new_if_all_archived(db: Session):
    """测试: 所有会话都归档时，应该创建新会话"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建并归档所有会话
    session_1 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 1"))
    m1 = Message(session_id=session_1.id, role="user", content="Test")
    m2 = Message(session_id=session_1.id, role="assistant", content="Test")
    db.add(m1)
    db.add(m2)
    db.commit()

    archive_session(db, session_1.id)
    db.refresh(session_1)
    assert session_1.memory_generated is True

    # 3. Action: 获取活跃会话
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 4. Assert: 应该创建并返回新的会话
    assert active_session.id != session_1.id
    assert active_session.friend_id == friend.id
    assert active_session.memory_generated is False


def test_archive_updates_update_time(db: Session):
    """测试: archive_session 应该更新 update_time 以防止误选"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建会话并获取初始 update_time
    session = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Test Session"))
    initial_update_time = session.update_time

    # 3. 给会话添加消息
    m1 = Message(session_id=session.id, role="user", content="Hello")
    m2 = Message(session_id=session.id, role="assistant", content="Hi")
    db.add(m1)
    db.add(m2)
    db.commit()

    # 4. 等待一小段时间确保时间戳不同
    import time
    time.sleep(0.01)

    # 5. Action: 归档会话
    archive_session(db, session.id)
    db.refresh(session)

    # 6. Assert: update_time 应该被更新
    assert session.update_time > initial_update_time
    assert session.memory_generated is True


def test_multiple_sessions_returns_highest_id(db: Session):
    """测试: 即使旧会话有更晚的 update_time，也应该返回 ID 最大的未归档会话"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建会话 1
    session_1 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 1"))

    # 3. 等待一小段时间
    import time
    time.sleep(0.01)

    # 4. 创建会话 2（ID 更大）
    session_2 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 2"))

    # 5. 给会话 1 添加消息，使其 update_time 比会话 2 更新
    m1 = Message(session_id=session_1.id, role="user", content="Hello")
    db.add(m1)
    db.commit()
    db.refresh(session_1)

    # 6. Action: 获取活跃会话
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 7. Assert: 应该返回 ID 更大的会话 2，即使会话 1 的 update_time 更新
    assert active_session.id == session_2.id
    assert active_session.id != session_1.id


def test_get_or_create_respects_non_deleted_filter(db: Session):
    """测试: 软删除的会话不应被选择"""
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 直接创建两个会话（不使用 create_session 避免自动归档）
    session_1 = ChatSession(friend_id=friend.id, title="Session 1")
    session_2 = ChatSession(friend_id=friend.id, title="Session 2")
    db.add(session_1)
    db.add(session_2)
    db.commit()
    db.refresh(session_1)
    db.refresh(session_2)

    # 3. 软删除会话 2
    session_2.deleted = True
    db.commit()

    # 4. Action: 获取活跃会话
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 5. Assert: 应该返回未删除的会话 1
    assert active_session.id == session_1.id
    assert active_session.deleted is False


def test_bug_scenario_manual_new_session(db: Session):
    """
    测试 Bug 场景：手动点击新建会话，然后发送消息
    应该返回新建的会话（ID 最大），而不是旧的会话
    """
    # 1. Setup: Create a friend
    friend = Friend(name="Test Friend", description="Test", system_prompt="You are helpful.")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    # 2. 创建会话 4（模拟之前存在的会话）
    session_4 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 4"))
    # 添加消息使其成为活跃会话
    m1 = Message(session_id=session_4.id, role="user", content="Previous chat")
    m2 = Message(session_id=session_4.id, role="assistant", content="Previous response")
    db.add(m1)
    db.add(m2)
    db.commit()

    # 3. 等待一小段时间
    import time
    time.sleep(0.01)

    # 4. 用户点击"新建会话"按钮，创建会话 5
    session_5 = create_session(db, ChatSessionCreate(friend_id=friend.id, title="Session 5"))
    db.refresh(session_5)

    # 5. 验证：会话 4 应该被归档
    db.refresh(session_4)
    assert session_4.memory_generated is True

    # 6. Action: 用户发送消息，后端调用 get_or_create_session_for_friend
    active_session = get_or_create_session_for_friend(db, friend_id=friend.id)

    # 7. Assert: 应该返回会话 5（新建的会话），而不是会话 4
    assert active_session.id == session_5.id
    assert active_session.id != session_4.id
    assert active_session.memory_generated is False
