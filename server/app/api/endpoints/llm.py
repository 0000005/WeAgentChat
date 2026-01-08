from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any
import logging

from app.api import deps
from app.schemas.llm import LLMConfig, LLMConfigUpdate
from app.services.llm_service import llm_service
from app.prompt import get_prompt

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/config", response_model=LLMConfig)
def get_llm_config(db: Session = Depends(deps.get_db)) -> Any:
    """
    Get the current LLM configuration.
    """
    config = llm_service.get_config(db)
    if not config:
        # Instead of 404, we might want to return a default empty structure or create a default one.
        # For now, let's return 404 if not configured, or we can decide to return an empty object.
        # Let's return a default "empty" config if none exists to avoid frontend errors on first load.
        # Or better, let the service handle "creation on default" if preferred.
        # But strictly speaking, if it's not there, it's not there.
        # Let's return 404 for now, and frontend can handle "no config set".
        raise HTTPException(status_code=404, detail="LLM Config not found")
    return config

@router.put("/config", response_model=LLMConfig)
def update_llm_config(
    config_in: LLMConfigUpdate,
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Update or create the LLM configuration.
    """
    config = llm_service.update_config(db, config_in)
    
    # Reload Memobase SDK config
    try:
        from app.services.memo import reload_sdk_config
        reload_sdk_config()
    except Exception as e:
        logger.warning(f"Failed to reload Memobase config: {e}")
        
    return config


@router.post("/config/test")
def test_llm_config(config_in: LLMConfigUpdate) -> dict:
    """
    Test the LLM configuration by sending a simple request.
    Uses the provided configuration parameters instead of database values.
    """
    if not config_in.api_key:
        raise HTTPException(status_code=400, detail="API Key is required for testing.")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=config_in.api_key,
            base_url=config_in.base_url if config_in.base_url else None
        )
        
        test_message = get_prompt("tests/llm_test_user_message.txt").strip()

        response = client.chat.completions.create(
            model=config_in.model_name or "gpt-3.5-turbo",
            messages=[{"role": "user", "content": test_message}],
            max_tokens=10
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
