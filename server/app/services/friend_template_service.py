from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.friend import Friend
from app.models.friend_template import FriendTemplate
from app.schemas.friend_template import FriendTemplateCreateFriend


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
        query = query.filter(
            FriendTemplate.tags.isnot(None),
            FriendTemplate.tags.like(f'%"{tag}"%'),
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
    return db_friend
