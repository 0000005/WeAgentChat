import logging
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.services.voice_service import get_voice_service
from app.schemas.voice import VoiceTimbreOut, VoiceTestRequest, VoiceTestResponse
from app.prompt import get_prompt

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_TTS_MODEL = "qwen3-tts-instruct-flash"


def _normalize_base_url(base_url: str | None) -> str:
    normalized = (base_url or DEFAULT_DASHSCOPE_BASE_URL).strip()
    if not normalized:
        normalized = DEFAULT_DASHSCOPE_BASE_URL
    return normalized.rstrip("/")


def _extract_audio_url(payload: dict) -> str | None:
    output = payload.get("output") or {}
    audio = output.get("audio") or {}
    return (
        audio.get("url")
        or output.get("audio_url")
        or output.get("url")
    )

@router.get("/timbres", response_model=List[VoiceTimbreOut])
def get_voice_timbres(db: Session = Depends(deps.get_db)):
    """获取所有可用音色列表"""
    service = get_voice_service(db)
    return service.get_all_timbres()


@router.post("/test", response_model=VoiceTestResponse)
def test_voice_config(
    payload: VoiceTestRequest,
    db: Session = Depends(deps.get_db),
):
    """
    测试语音配置可用性，并返回可播放音频 URL。
    """
    service = get_voice_service(db)
    if not service.get_timbre_by_voice_id(payload.voice_id):
        raise HTTPException(status_code=400, detail=f"音色不存在：{payload.voice_id}")

    model = (payload.model or DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL
    base_url = _normalize_base_url(payload.base_url)
    endpoint = f"{base_url}/services/aigc/multimodal-generation/generation"
    text = (payload.text or get_prompt("tests/voice_test_text.txt")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="测试文本不能为空")
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    request_body = {
        "model": model,
        "input": {
            "text": text,
            "voice": payload.voice_id,
            "language_type": "Chinese",
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(endpoint, json=request_body, headers=headers)
    except Exception as exc:
        logger.error(f"Voice test request failed: {exc}")
        raise HTTPException(status_code=400, detail=f"语音测试失败：{str(exc)}")

    if response.status_code != 200:
        try:
            error_payload = response.json()
            detail = error_payload.get("message") or error_payload.get("detail") or response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=400, detail=f"语音测试失败：{detail}")

    try:
        response_payload = response.json()
    except Exception:
        raise HTTPException(status_code=400, detail="语音测试失败：响应格式无效")

    audio_url = _extract_audio_url(response_payload)
    if not audio_url:
        raise HTTPException(status_code=400, detail="语音测试失败：未返回可播放音频 URL")

    return VoiceTestResponse(
        success=True,
        message="测试成功",
        model=model,
        voice_id=payload.voice_id,
        audio_url=audio_url,
    )
