from fastapi import APIRouter, Depends, HTTPException, Body, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.api import deps
from app.schemas import group_auto_drive as ad_schemas
from app.services.group_auto_drive_service import group_auto_drive_service
from app.services.memo.constants import DEFAULT_USER_ID
from app.models.group import GroupMember

router = APIRouter()


@router.post("/group/auto-drive/start", response_model=ad_schemas.AutoDriveStateRead)
async def start_auto_drive(
    *,
    db: Session = Depends(deps.get_db),
    payload: ad_schemas.AutoDriveStartRequest,
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == payload.group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    try:
        return await group_auto_drive_service.start_auto_drive(
            db,
            payload.group_id,
            payload.config,
            enable_thinking=payload.enable_thinking,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/group/auto-drive/stream")
async def stream_auto_drive(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int = Query(...),
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    async def event_generator():
        async for event_data in group_auto_drive_service.stream_auto_drive(group_id):
            event_type = event_data.get("event", "message")
            data_payload = event_data.get("data", {})
            json_data = json.dumps(data_payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {json_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/group/auto-drive/pause", response_model=ad_schemas.AutoDriveStateRead)
async def pause_auto_drive(
    *,
    db: Session = Depends(deps.get_db),
    payload: ad_schemas.AutoDriveActionRequest,
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == payload.group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    try:
        return await group_auto_drive_service.pause_auto_drive(db, payload.group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group/auto-drive/resume", response_model=ad_schemas.AutoDriveStateRead)
async def resume_auto_drive(
    *,
    db: Session = Depends(deps.get_db),
    payload: ad_schemas.AutoDriveActionRequest,
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == payload.group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    try:
        return await group_auto_drive_service.resume_auto_drive(db, payload.group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/group/auto-drive/stop", response_model=ad_schemas.AutoDriveStateRead)
async def stop_auto_drive(
    *,
    db: Session = Depends(deps.get_db),
    payload: ad_schemas.AutoDriveActionRequest,
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == payload.group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    try:
        return await group_auto_drive_service.stop_auto_drive(db, payload.group_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/group/auto-drive/state", response_model=ad_schemas.AutoDriveStateRead)
def get_auto_drive_state(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int = Query(...),
):
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    state = group_auto_drive_service.get_state(db, group_id)
    if not state:
        return Response(status_code=204)
    return state


