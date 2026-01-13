import json
from typing import List, Optional

from sqlalchemy import or_

from sqlalchemy.orm import Session

from app.models.friend import Friend
from app.models.friend_template import FriendTemplate
from app.schemas.friend_template import FriendTemplateCreateFriend
from app.services import friend_service


def get_friend_template(db: Session, template_id: int) -> Optional[FriendTemplate]:
    return db.query(FriendTemplate).filter(FriendTemplate.id == template_id).first()


def get_friend_templates(
    db: Session,
    page: int = 1,
    size: int = 20,
    tag: Optional[str] = None,
    q: Optional[str] = None,
) -> List[FriendTemplate]:
    query = db.query(FriendTemplate)
    if tag:
        # 兼容逗号分隔的字符串存储
        pattern = f"%{tag}%"
        query = query.filter(
            FriendTemplate.tags.isnot(None),
            FriendTemplate.tags.like(pattern),
        )
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                FriendTemplate.name.like(pattern),
                FriendTemplate.description.like(pattern),
            )
        )
    return (
        query.order_by(FriendTemplate.updated_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )


def create_friend_from_template(db: Session, template_id: int) -> Optional[Friend]:
    template = get_friend_template(db, template_id)
    if not template:
        return None
    db_friend = Friend(
        name=template.name,
        description=template.description,
        system_prompt=template.system_prompt,
        is_preset=False,
        avatar=template.avatar,
    )
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    # 创建初始招呼消息
    friend_service.ensure_initial_message(db, db_friend.id, template.initial_message)
    return db_friend


def create_friend_from_payload(db: Session, payload: FriendTemplateCreateFriend) -> Friend:
    db_friend = Friend(
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        is_preset=False,
        avatar=payload.avatar,
    )
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    # 创建初始招呼消息
    friend_service.ensure_initial_message(db, db_friend.id, payload.initial_message)
    return db_friend


def get_all_tags(db: Session) -> List[str]:
    """
    获取所有不重复的标签
    """
    templates = db.query(FriendTemplate.tags).filter(FriendTemplate.tags.isnot(None)).all()
    tag_set = set()
    for (tags_val,) in templates:
        if not tags_val:
            continue
        
        # 尝试处理 JSON
        if isinstance(tags_val, str) and tags_val.startswith("["):
            try:
                tags_list = json.loads(tags_val)
                if isinstance(tags_list, list):
                    for t in tags_list:
                        if t: tag_set.add(str(t).strip())
                    continue
            except json.JSONDecodeError:
                pass
        
        # 处理逗号分隔
        if isinstance(tags_val, str):
            parts = [t.strip() for t in tags_val.split(",") if t.strip()]
            for p in parts:
                tag_set.add(p)
    
    return sorted(list(tag_set), key=lambda x: x.encode('gbk') if x else '')

