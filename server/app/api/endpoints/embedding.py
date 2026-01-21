from typing import Any, List
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.embedding import EmbeddingSetting, EmbeddingSettingCreate, EmbeddingSettingUpdate
from app.services.embedding_service import embedding_service
from app.services.settings_service import SettingsService
from app.prompt import get_prompt

logger = logging.getLogger(__name__)

router = APIRouter()
MAX_EMBEDDING_CONFIGS = 20

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
    if embedding_service.count_settings(db) >= MAX_EMBEDDING_CONFIGS:
        raise HTTPException(status_code=400, detail="Embedding 配置数量已达上限（20）")
    item = embedding_service.create_setting(db=db, obj_in=item_in)

    active_id = SettingsService.get_setting(db, "memory", "active_embedding_config_id", None)
    if active_id is None:
        SettingsService.set_setting(
            db,
            "memory",
            "active_embedding_config_id",
            item.id,
            "int",
            "当前向量模型配置ID",
        )
    
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
    active_id = SettingsService.get_setting(db, "memory", "active_embedding_config_id", None)
    if active_id == id:
        raise HTTPException(status_code=400, detail="该配置当前正在被记忆模块使用，请先切换到其他配置后再删除。")

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


@router.post("/test")
def test_embedding_config(config_in: EmbeddingSettingCreate) -> dict:
    """
    Test the Embedding configuration by sending a simple request.
    Uses the provided configuration parameters instead of database values.
    """
    if not config_in.embedding_api_key:
        raise HTTPException(status_code=400, detail="API Key is required for testing.")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=config_in.embedding_api_key,
            base_url=config_in.embedding_base_url if config_in.embedding_base_url else None
        )
        
        test_input = get_prompt("tests/embedding_test_input.txt").strip()

        response = client.embeddings.create(
            model=config_in.embedding_model or "text-embedding-ada-002",
            input=test_input,
        )
        
        embedding_dim = len(response.data[0].embedding) if response.data else 0
        
        return {
            "success": True,
            "message": "Embedding connection test successful!",
            "model": response.model,
            "dimension": embedding_dim
        }
    except Exception as e:
        logger.error(f"Embedding test failed: {e}")
        raise HTTPException(status_code=400, detail=f"Embedding test failed: {str(e)}")
