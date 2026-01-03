from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas import friend as friend_schemas
from app.services import friend_service

router = APIRouter()

@router.get("/", response_model=List[friend_schemas.Friend])
def read_friends(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve friends.
    """
    friends = friend_service.get_friends(db, skip=skip, limit=limit)
    return friends

@router.post("/", response_model=friend_schemas.Friend)
def create_friend(
    *,
    db: Session = Depends(deps.get_db),
    friend_in: friend_schemas.FriendCreate,
):
    """
    Create new friend.
    """
    friend = friend_service.create_friend(db, friend=friend_in)
    return friend

@router.get("/{friend_id}", response_model=friend_schemas.Friend)
def read_friend(
    *,
    db: Session = Depends(deps.get_db),
    friend_id: int,
):
    """
    Get friend by ID.
    """
    friend = friend_service.get_friend(db, friend_id=friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    return friend

@router.put("/{friend_id}", response_model=friend_schemas.Friend)
def update_friend(
    *,
    db: Session = Depends(deps.get_db),
    friend_id: int,
    friend_in: friend_schemas.FriendUpdate,
):
    """
    Update a friend.
    """
    friend = friend_service.update_friend(db, friend_id=friend_id, friend_in=friend_in)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    return friend

@router.delete("/{friend_id}", response_model=friend_schemas.Friend)
def delete_friend(
    *,
    db: Session = Depends(deps.get_db),
    friend_id: int,
):
    """
    Delete a friend.
    """
    friend = friend_service.get_friend(db, friend_id=friend_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend not found")
    
    success = friend_service.delete_friend(db, friend_id=friend_id)
    if not success:
         raise HTTPException(status_code=500, detail="Failed to delete friend")
         
    return friend
