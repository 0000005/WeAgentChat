from typing import Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.embedding import EmbeddingSetting, EmbeddingSettingCreate, EmbeddingSettingUpdate
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[EmbeddingSetting])
def read_embedding_settings(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve embedding settings.
    """
    settings = embedding_service.get_multi(db, skip=skip, limit=limit)
    return settings

@router.post("/", response_model=EmbeddingSetting)
def create_embedding_setting(
    *,
    db: Session = Depends(deps.get_db),
    item_in: EmbeddingSettingCreate,
) -> Any:
    """
    Create new embedding setting.
    """
    item = embedding_service.create_setting(db=db, obj_in=item_in)
    
    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return item

@router.get("/{id}", response_model=EmbeddingSetting)
def read_embedding_setting(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
) -> Any:
    """
    Get embedding setting by ID.
    """
    item = embedding_service.get_setting(db=db, setting_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Embedding setting not found")
    return item

@router.put("/{id}", response_model=EmbeddingSetting)
def update_embedding_setting(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
    item_in: EmbeddingSettingUpdate,
) -> Any:
    """
    Update an embedding setting.
    """
    item = embedding_service.get_setting(db=db, setting_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Embedding setting not found")
    item = embedding_service.update_setting(db=db, db_obj=item, obj_in=item_in)
    
    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return item

@router.delete("/{id}", response_model=EmbeddingSetting)
def delete_embedding_setting(
    *,
    db: Session = Depends(deps.get_db),
    id: int,
) -> Any:
    """
    Delete an embedding setting.
    """
    item = embedding_service.get_setting(db=db, setting_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Embedding setting not found")
    item = embedding_service.delete_setting(db=db, db_obj=item)
    
    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return item
