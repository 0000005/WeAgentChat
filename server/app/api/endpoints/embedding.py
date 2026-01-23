from typing import Any, List
import logging
import httpx

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

def _normalize_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    return base_url.rstrip("/")


def _normalize_ollama_base_url(base_url: str | None) -> str:
    normalized = _normalize_base_url(base_url) or "http://127.0.0.1:11434"
    if normalized.endswith("/api"):
        normalized = normalized[:-4]
    return normalized

def _build_auth_headers(api_key: str | None) -> dict:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}

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
    provider = (config_in.embedding_provider or "openai").lower()
    test_input = get_prompt("tests/embedding_test_input.txt").strip()
    model_name = config_in.embedding_model or "text-embedding-ada-002"

    try:
        if provider == "openai":
            if not config_in.embedding_api_key:
                raise HTTPException(status_code=400, detail="API Key is required for testing.")

            # Pre-check: Warn if base_url looks incomplete (missing /v1 path for known providers)
            base_url = _normalize_base_url(config_in.embedding_base_url)
            if base_url:
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                path = parsed.path.strip("/")
                known_providers_requiring_path = {
                    "api.siliconflow.cn": "/v1",
                    "open.bigmodel.cn": "/api/paas/v4",
                    "api.openai.com": "/v1",
                }
                for host, expected_path in known_providers_requiring_path.items():
                    if host in (parsed.netloc or ""):
                        if not path or path == "":
                            raise HTTPException(
                                status_code=400,
                                detail=f"Base URL 格式不完整。对于 {host}，请使用完整路径，例如：https://{host}{expected_path}"
                            )

            from openai import OpenAI

            client = OpenAI(
                api_key=config_in.embedding_api_key,
                base_url=base_url
            )


            response = client.embeddings.create(
                model=model_name,
                input=test_input,
            )

            if not response.data:
                raise HTTPException(status_code=400, detail="Embedding test failed: No embedding data received")

            embedding_dim = len(response.data[0].embedding)
            return {
                "success": True,
                "message": "Embedding connection test successful!",
                "model": response.model,
                "dimension": embedding_dim
            }

        if provider == "jina":
            if not config_in.embedding_api_key:
                raise HTTPException(status_code=400, detail="API Key is required for testing.")
            base_url = _normalize_base_url(config_in.embedding_base_url)
            if not base_url:
                raise HTTPException(status_code=400, detail="Base URL is required for Jina.")

            with httpx.Client(base_url=base_url, headers=_build_auth_headers(config_in.embedding_api_key)) as client:
                response = client.post(
                    "/embeddings",
                    json={
                        "model": model_name,
                        "input": [test_input],
                        "dimensions": config_in.embedding_dim
                    },
                    timeout=20,
                )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Embedding test failed: {response.text}")
            data = response.json()
            embeddings = data.get("data") or []
            embedding = embeddings[0].get("embedding") if embeddings else None
            if not embedding:
                raise HTTPException(status_code=400, detail="Embedding test failed: No embedding data received")

            return {
                "success": True,
                "message": "Embedding connection test successful!",
                "model": data.get("model") or model_name,
                "dimension": len(embedding)
            }

        if provider == "lmstudio":
            base_url = _normalize_base_url(config_in.embedding_base_url)
            if not base_url:
                raise HTTPException(status_code=400, detail="Base URL is required for LMStudio.")

            with httpx.Client(base_url=base_url, headers=_build_auth_headers(config_in.embedding_api_key)) as client:
                response = client.post(
                    "/embeddings",
                    json={
                        "model": model_name,
                        "input": [test_input],
                        "task": "retrieval.passage",
                        "truncate": True,
                        "dimensions": config_in.embedding_dim
                    },
                    timeout=20,
                )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Embedding test failed: {response.text}")
            data = response.json()
            embeddings = data.get("data") or []
            embedding = embeddings[0].get("embedding") if embeddings else None
            if not embedding:
                raise HTTPException(status_code=400, detail="Embedding test failed: No embedding data received")

            return {
                "success": True,
                "message": "Embedding connection test successful!",
                "model": data.get("model") or model_name,
                "dimension": len(embedding)
            }

        if provider == "ollama":
            base_url = _normalize_ollama_base_url(config_in.embedding_base_url)
            with httpx.Client(base_url=base_url, headers=_build_auth_headers(config_in.embedding_api_key)) as client:
                response = client.post(
                    "/api/embed",
                    json={
                        "model": model_name,
                        "input": [test_input],
                        "truncate": True,
                        "dimensions": config_in.embedding_dim,
                    },
                    timeout=20,
                )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Embedding test failed: {response.text}")
            data = response.json()
            embeddings = data.get("embeddings") or []
            embedding = embeddings[0] if embeddings else None
            if not embedding:
                raise HTTPException(status_code=400, detail="Embedding test failed: No embedding data received")

            return {
                "success": True,
                "message": "Embedding connection test successful!",
                "model": data.get("model") or model_name,
                "dimension": len(embedding)
            }

        raise HTTPException(status_code=400, detail=f"Unsupported embedding provider: {provider}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding test failed: {e}")
        raise HTTPException(status_code=400, detail=f"Embedding test failed: {str(e)}")
