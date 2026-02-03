import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas import friend as friend_schemas
from app.schemas import friend_template as friend_template_schemas
from app.schemas import persona_generator as persona_schemas
from app.services import friend_template_service
from app.services.persona_generator_service import persona_generator_service

router = APIRouter()


@router.get("/", response_model=List[friend_template_schemas.FriendTemplate])
def read_friend_templates(
    db: Session = Depends(deps.get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    tag: Optional[str] = None,
    q: Optional[str] = None,
):
    return friend_template_service.get_friend_templates(
        db,
        page=page,
        size=size,
        tag=tag,
        q=q,
    )



@router.get("/tags", response_model=List[str])
def read_friend_template_tags(
    db: Session = Depends(deps.get_db),
):
    return friend_template_service.get_all_tags(db)


@router.post("/{template_id}/clone", response_model=friend_schemas.Friend)
def clone_friend_template(
    *,
    db: Session = Depends(deps.get_db),
    template_id: int,
):
    friend = friend_template_service.create_friend_from_template(db, template_id)
    if not friend:
        raise HTTPException(status_code=404, detail="Friend template not found")
    return friend


@router.post("/create-friend", response_model=friend_schemas.Friend)
def create_friend_from_template(
    *,
    db: Session = Depends(deps.get_db),
    payload: friend_template_schemas.FriendTemplateCreateFriend,
):
    return friend_template_service.create_friend_from_payload(db, payload)


@router.post("/generate/stream")
async def generate_persona_stream(
    *,
    db: Session = Depends(deps.get_db),
    payload: persona_schemas.PersonaGenerateRequest,
):
    """
    根据描述自动生成 Persona 设定（SSE 流式）
    """
    async def event_generator():
        async for event_data in persona_generator_service.generate_persona_stream(db, payload):
            event_type = event_data.get("event", "delta")
            data_payload = event_data.get("data", {})
            json_data = json.dumps(data_payload, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {json_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
