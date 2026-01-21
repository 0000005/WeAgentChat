from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, List
import logging

from app.api import deps
from app.schemas.llm import LLMConfig, LLMConfigRead, LLMConfigUpdate, LLMConfigCreate
from app.services.llm_service import llm_service
from app.services.settings_service import SettingsService
from app.prompt import get_prompt

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LLM_CONFIGS = 20

@router.get("/configs", response_model=List[LLMConfig])
def read_llm_configs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve LLM configurations.
    """
    return llm_service.get_multi(db, skip=skip, limit=limit)

@router.post("/configs", response_model=LLMConfig)
def create_llm_config(
    config_in: LLMConfigCreate,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Create a new LLM configuration.
    """
    if llm_service.count_configs(db) >= MAX_LLM_CONFIGS:
        raise HTTPException(status_code=400, detail="LLM 配置数量已达上限（20）")
    config = llm_service.create_config(db, config_in)

    active_id = SettingsService.get_setting(db, "chat", "active_llm_config_id", None)
    if active_id is None:
        SettingsService.set_setting(
            db,
            "chat",
            "active_llm_config_id",
            config.id,
            "int",
            "当前聊天模型配置ID",
        )

    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return config

@router.put("/configs/{id}", response_model=LLMConfig)
def update_llm_config_by_id(
    id: int,
    config_in: LLMConfigUpdate,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Update an LLM configuration by ID.
    """
    config = llm_service.update_config(db, id, config_in)
    if not config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")

    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return config

@router.delete("/configs/{id}", response_model=LLMConfig)
def delete_llm_config(
    id: int,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Delete an LLM configuration.
    """
    active_id = SettingsService.get_setting(db, "chat", "active_llm_config_id", None)
    if active_id == id:
        raise HTTPException(status_code=400, detail="该配置当前正在被聊天模块使用，请先切换到其他配置后再删除。")

    config = llm_service.get_config_by_id(db, id)
    if not config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")
    config = llm_service.delete_config(db, config)

    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")

    return config

@router.post("/configs/{id}/test")
def test_llm_config_by_id(
    id: int,
    db: Session = Depends(deps.get_db),
) -> dict:
    """
    Test the LLM configuration by ID.
    """
    config = llm_service.get_config_by_id(db, id)
    if not config:
        raise HTTPException(status_code=404, detail="LLM configuration not found")

    return _test_llm_config_payload(
        base_url=config.base_url,
        api_key=config.api_key,
        model_name=config.model_name,
    )

@router.get("/config", response_model=LLMConfigRead)
def get_llm_config(db: Session = Depends(deps.get_db)) -> Any:
    """
    Get the current LLM configuration.
    """
    config = llm_service.get_active_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="LLM Config not found")
    return config

@router.put("/config", response_model=LLMConfig)
def update_llm_config(
    config_in: LLMConfigUpdate,
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Update or create the active LLM configuration.
    """
    existing = llm_service.get_active_config(db)
    if existing:
        config = llm_service.update_config(db, existing.id, config_in)
    else:
        if llm_service.count_configs(db) >= MAX_LLM_CONFIGS:
            raise HTTPException(status_code=400, detail="LLM 配置数量已达上限（20）")
        config = llm_service.create_config(db, LLMConfigCreate(**config_in.model_dump()))
        SettingsService.set_setting(
            db,
            "chat",
            "active_llm_config_id",
            config.id,
            "int",
            "当前聊天模型配置ID",
        )
    
    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")
        
    return config


def _test_llm_config_payload(base_url: str | None, api_key: str | None, model_name: str | None) -> dict:
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required for testing.")

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )

        test_message = get_prompt("tests/llm_test_user_message.txt").strip()

        response = client.chat.completions.create(
            model=model_name or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": test_message}]
        )

        return {
            "success": True,
            "message": "LLM connection test successful!",
            "model": response.model,
            "response": response.choices[0].message.content if response.choices else None
        }
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        raise HTTPException(status_code=400, detail=f"LLM test failed: {str(e)}")


@router.post("/config/test")
def test_llm_config(config_in: LLMConfigUpdate) -> dict:
    """
    Test the LLM configuration by sending a simple request.
    Uses the provided configuration parameters instead of database values.
    """
    return _test_llm_config_payload(
        base_url=config_in.base_url,
        api_key=config_in.api_key,
        model_name=config_in.model_name,
    )
