from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timezone
from app.models.friend import Friend
from app.models.chat import ChatSession, Message
from app.schemas.friend import FriendCreate, FriendUpdate

def get_friend(db: Session, friend_id: int) -> Optional[Friend]:
    return db.query(Friend).filter(Friend.id == friend_id, Friend.deleted == False).first()

import re

def _strip_message_tags(content: Optional[str]) -> Optional[str]:
    if not content:
        return content
    # 提取所有 <message> 标签内容并用空格合并
    parts = re.findall(r'<message>(.*?)</message>', content, re.DOTALL)
    if parts:
        return " ".join(part.strip() for part in parts if part.strip())
    # 兜底：如果没有匹配到完整标签但包含标签字符，直接剔除所有标签文本
    return re.sub(r'</?message>', '', content).strip()

def get_friends(db: Session, skip: int = 0, limit: int = 100) -> List[Friend]:
    # 子查询：获取每个好友的最新消息ID（通过 ChatSession 连接）
    latest_message_subquery = (
        db.query(
            ChatSession.friend_id,
            func.max(Message.id).label("max_id")
        )
        .join(Message, ChatSession.id == Message.session_id)
        .filter(Message.deleted == False, ChatSession.deleted == False)
        .group_by(ChatSession.friend_id)
        .subquery()
    )

    # 主查询：连接好友和最新消息
    query = (
        db.query(Friend, Message.content, Message.role, Message.create_time)
        .outerjoin(latest_message_subquery, Friend.id == latest_message_subquery.c.friend_id)
        .outerjoin(Message, Message.id == latest_message_subquery.c.max_id)
        .filter(Friend.deleted == False)
        # 排序：置顶优先，其次按最后消息时间，最后按更新时间
        .order_by(
            Friend.pinned_at.desc().nulls_last(), 
            Message.create_time.desc().nulls_last(), 
            Friend.update_time.desc()
        )
        .offset(skip)
        .limit(limit)
    )

    results = []
    for friend, content, role, msg_time in query.all():
        # 将消息内容绑定到 friend 对象（临时属性，以便 Pydantic 转换）
        friend.last_message = _strip_message_tags(content)
        friend.last_message_role = role
        friend.last_message_time = msg_time
        results.append(friend)
    
    return results

def create_friend(db: Session, friend: FriendCreate) -> Friend:
    db_friend = Friend(
        name=friend.name,
        description=friend.description,
        system_prompt=friend.system_prompt,
        is_preset=friend.is_preset
    )
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    return db_friend

def update_friend(db: Session, friend_id: int, friend_in: FriendUpdate) -> Optional[Friend]:
    db_friend = get_friend(db, friend_id)
    if not db_friend:
        return None
    
    update_data = friend_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_friend, field, value)
    
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    return db_friend

def delete_friend(db: Session, friend_id: int) -> bool:
    db_friend = get_friend(db, friend_id)
    if not db_friend:
        return False
    
    # 逻辑删除
    db_friend.deleted = True
    db.add(db_friend)
    db.commit()
    return True

def ensure_initial_message(db: Session, friend_id: int, initial_message: Optional[str] = None) -> Optional[Message]:
    """
    确保好友有初始招呼消息。如果没有 session，则创建一个并添加初始消息。
    """
    # 检查是否已有 session
    existing_session = db.query(ChatSession).filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False).first()
    if existing_session:
        return None

    if not initial_message:
        initial_message = "你好！很高兴见到你。"

    # 创建 session
    db_session = ChatSession(
        friend_id=friend_id,
        title="新对话",
        last_message_time=datetime.now(timezone.utc)
    )
    db.add(db_session)
    db.flush() # 获取 ID

    # 创建消息
    db_message = Message(
        session_id=db_session.id,
        friend_id=friend_id,
        role="assistant",
        content=initial_message
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message
