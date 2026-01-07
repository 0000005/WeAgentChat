from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.friend import Friend
from app.schemas.friend import FriendCreate, FriendUpdate

def get_friend(db: Session, friend_id: int) -> Optional[Friend]:
    return db.query(Friend).filter(Friend.id == friend_id, Friend.deleted == False).first()

def get_friends(db: Session, skip: int = 0, limit: int = 100) -> List[Friend]:
    return (
        db.query(Friend)
        .filter(Friend.deleted == False)
        .order_by(Friend.pinned_at.desc().nulls_last(), Friend.update_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

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
