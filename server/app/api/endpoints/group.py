from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas import group as group_schemas
from app.services.group_service import group_service
from app.services.memo.constants import DEFAULT_USER_ID

router = APIRouter()

@router.get("/groups", response_model=List[group_schemas.GroupReadWithMembers])
def read_user_groups(
    db: Session = Depends(deps.get_db),
):
    """
    获取当前用户加入的所有群组。
    """
    return group_service.get_user_groups(db)

@router.post("/group/create", response_model=group_schemas.GroupReadWithMembers)
def create_group(
    *,
    db: Session = Depends(deps.get_db),
    group_in: group_schemas.GroupCreate,
):
    """
    创建新群组。
    """
    return group_service.create_group(db, group_in)

@router.get("/group/{id}", response_model=group_schemas.GroupReadWithMembers)
def read_group(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
):
    """
    获取群详情及成员列表。
    """
    group = group_service.get_group(db, id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is a member
    if not group_service.is_member(db, id, DEFAULT_USER_ID):
        raise HTTPException(status_code=403, detail="Not a member of this group")
        
    return group

@router.post("/group/invite", response_model=bool)
def invite_members(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int = Body(...),
    member_ids: List[str] = Body(...),
):
    """
    向现有群组添加新成员。
    """
    success = group_service.add_members(db, group_id, member_ids)
    if not success:
        raise HTTPException(status_code=403, detail="Failed to invite members")
    return True

@router.patch("/group/settings", response_model=group_schemas.GroupRead)
def update_group_settings(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int = Body(...),
    group_in: group_schemas.GroupUpdate = Body(...),
):
    """
    更新群设置。仅群主可操作。
    """
    group = group_service.update_group(db, group_id, group_in)
    if not group:
        raise HTTPException(status_code=403, detail="Not authorized or group not found")
    return group

@router.delete("/group/exit", response_model=bool)
def exit_group(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int = Query(...),
):
    """
    当前用户退出群组。
    """
    success = group_service.exit_group(db, group_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to exit group")
    return True

@router.delete("/group/{id}/member/{member_id}", response_model=bool)
def remove_group_member(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    member_id: str,
):
    """
    群主移除指定群成员。
    """
    success = group_service.remove_member(db, id, member_id)
    if not success:
        raise HTTPException(status_code=403, detail="Not authorized or member not found")
    return True

# --- Group Chat Messaging ---

@router.get("/group/{id}/messages", response_model=List[group_schemas.GroupMessageRead])
def read_group_messages(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    skip: int = 0,
    limit: int = 100,
):
    """
    获取群组历史消息。
    """
    from app.models.group import GroupMessage, GroupMember
    
    # 鉴权：检查当前用户是否在群组中
    member = db.query(GroupMember).filter(
        GroupMember.group_id == id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user"
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    messages = db.query(GroupMessage).filter(GroupMessage.group_id == id).order_by(GroupMessage.create_time.desc()).offset(skip).limit(limit).all()
    return list(reversed(messages))


