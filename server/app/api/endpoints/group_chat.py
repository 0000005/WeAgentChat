from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from app.api import deps
from app.schemas import group as group_schemas
from app.services.group_chat_service import group_chat_service
from app.services.memo.constants import DEFAULT_USER_ID
from app.models.group import GroupMember

router = APIRouter()

@router.post("/group/{group_id}/messages")
async def send_group_message_stream(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int,
    message_in: group_schemas.GroupMessageCreate,
):
    """
    发送群消息并流式获取 AI 响应。
    """
    # 鉴权：检查当前用户是否在群组中
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user"
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    async def event_generator():
        async for event_data in group_chat_service.send_group_message_stream(db, group_id, message_in):
            event_type = event_data.get("event", "message")
            data_payload = event_data.get("data", {})
            json_data = json.dumps(data_payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {json_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.delete("/group/{group_id}/messages")
async def clear_group_messages(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int,
):
    """
    清空群消息记录。
    """
    # 鉴权：检查当前用户是否在群组中
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.member_id == DEFAULT_USER_ID,
        GroupMember.member_type == "user"
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    group_chat_service.clear_group_messages(db, group_id)
    return {"message": "Success"}
