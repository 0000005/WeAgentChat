import asyncio
import logging
import math
import os
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_TTS_MODEL = "qwen3-tts-instruct-flash"
VOICE_ENDPOINT = "/services/aigc/multimodal-generation/generation"
MAX_TTS_PARALLELISM = 4


def parse_message_segments(content: str) -> List[str]:
    """
    按 <message> 标签切分文本；若不存在标签，返回整段文本。
    与前端 parseMessageSegments 保持一致，确保 segment_index 可对齐。
    """
    if not content:
        return []

    if "<message>" not in content:
        text = content.strip()
        return [text] if text else []

    import re

    regex = re.compile(r"<message>([\s\S]*?)</message>")
    segments: List[str] = []
    last_index = 0
    for match in regex.finditer(content):
        text = (match.group(1) or "").strip()
        if text:
            segments.append(text)
        last_index = match.end()

    remaining = content[last_index:]
    if "<message>" in remaining:
        open_tag_index = remaining.find("<message>")
        trailing = remaining[open_tag_index + len("<message>") :].strip()
        if trailing:
            segments.append(trailing)

    if not segments:
        text = content.strip()
        return [text] if text else []
    return segments


def _normalize_base_url(base_url: Optional[str]) -> str:
    normalized = (base_url or DEFAULT_DASHSCOPE_BASE_URL).strip()
    if not normalized:
        normalized = DEFAULT_DASHSCOPE_BASE_URL
    return normalized.rstrip("/")


def _extract_audio_url(payload: Dict[str, Any]) -> Optional[str]:
    output = payload.get("output") or {}
    audio = output.get("audio") or {}
    return (
        audio.get("url")
        or output.get("audio_url")
        or output.get("url")
    )


def _estimate_duration_seconds(text: str) -> int:
    # 粗略估算：中文 TTS 约 4~5 字/秒
    if not text:
        return 1
    return max(1, min(60, math.ceil(len(text) / 4.5)))


def _try_read_wav_duration_seconds(file_path: str) -> Optional[int]:
    try:
        with wave.open(file_path, "rb") as wav:
            frames = wav.getnframes()
            framerate = wav.getframerate()
            if framerate <= 0:
                return None
            return max(1, int(round(frames / float(framerate))))
    except Exception:
        return None


def _infer_extension(audio_url: str, content_type: Optional[str]) -> str:
    suffix = Path(urlparse(audio_url).path).suffix.lower()
    if suffix in {".mp3", ".wav", ".aac", ".ogg", ".m4a"}:
        return suffix

    ctype = (content_type or "").lower()
    if "wav" in ctype:
        return ".wav"
    if "ogg" in ctype:
        return ".ogg"
    if "aac" in ctype:
        return ".aac"
    if "m4a" in ctype or "mp4" in ctype:
        return ".m4a"
    return ".mp3"


def _build_audio_output_path(message_id: int, segment_index: int, ext: str) -> tuple[str, str]:
    day_bucket = datetime.now(timezone.utc).strftime("%Y%m%d")
    rel_dir = os.path.join("audio", day_bucket)
    abs_dir = os.path.join(settings.DATA_DIR, "uploads", rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"msg{message_id}_seg{segment_index}_{uuid.uuid4().hex[:8]}{ext}"
    abs_path = os.path.join(abs_dir, filename)
    rel_url = f"/uploads/{rel_dir.replace(os.sep, '/')}/{filename}"
    return abs_path, rel_url


def resolve_voice_runtime_config(db: Session) -> Optional[Dict[str, str]]:
    api_key = str(SettingsService.get_setting(db, "voice", "api_key", "") or "").strip()
    if not api_key:
        return None

    model = str(SettingsService.get_setting(db, "voice", "tts_model", DEFAULT_TTS_MODEL) or DEFAULT_TTS_MODEL).strip()
    if not model:
        model = DEFAULT_TTS_MODEL

    base_url_raw = SettingsService.get_setting(db, "voice", "base_url", None)
    base_url = _normalize_base_url(str(base_url_raw) if isinstance(base_url_raw, str) else None)

    default_voice_id = str(SettingsService.get_setting(db, "voice", "default_voice_id", "") or "").strip()

    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "default_voice_id": default_voice_id,
    }


async def _synthesize_single_segment(
    client: httpx.AsyncClient,
    segment_text: str,
    segment_index: int,
    *,
    message_id: int,
    model: str,
    base_url: str,
    api_key: str,
    voice_id: str,
) -> Dict[str, Any]:
    endpoint = f"{base_url}{VOICE_ENDPOINT}"
    request_body = {
        "model": model,
        "input": {
            "text": segment_text,
            "voice": voice_id,
            "language_type": "Chinese",
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = await client.post(endpoint, json=request_body, headers=headers)
    response.raise_for_status()
    payload = response.json()

    remote_audio_url = _extract_audio_url(payload)
    if not remote_audio_url:
        raise ValueError("TTS 响应中未找到 audio url")

    audio_resp = await client.get(remote_audio_url)
    audio_resp.raise_for_status()

    ext = _infer_extension(remote_audio_url, audio_resp.headers.get("content-type"))
    abs_path, rel_url = _build_audio_output_path(message_id, segment_index, ext)
    with open(abs_path, "wb") as f:
        f.write(audio_resp.content)

    duration = None
    if ext == ".wav":
        duration = _try_read_wav_duration_seconds(abs_path)
    if duration is None:
        duration = _estimate_duration_seconds(segment_text)

    return {
        "segment_index": segment_index,
        "text": segment_text,
        "audio_url": rel_url,
        "duration_sec": duration,
    }


async def generate_voice_payload_for_message(
    db: Session,
    *,
    content: str,
    enable_voice: bool,
    friend_voice_id: Optional[str],
    message_id: int,
    on_segment_ready: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    为消息生成语音 payload。
    返回格式:
    {
      "voice_id": "...",
      "segments": [{segment_index, text, audio_url, duration_sec}, ...],
      "generated_at": "..."
    }
    """
    if not enable_voice:
        return None

    runtime_config = resolve_voice_runtime_config(db)
    if not runtime_config:
        logger.info("[Voice] Skip voice generation: global voice config incomplete.")
        return None

    voice_id = (friend_voice_id or runtime_config["default_voice_id"] or "").strip()
    if not voice_id:
        logger.info("[Voice] Skip voice generation: no voice_id resolved for message=%s", message_id)
        return None

    segments = parse_message_segments(content)
    if not segments:
        return None

    model = runtime_config["model"]
    base_url = runtime_config["base_url"]
    api_key = runtime_config["api_key"]

    semaphore = asyncio.Semaphore(MAX_TTS_PARALLELISM)
    collected: Dict[int, Dict[str, Any]] = {}

    async def _worker(seg_text: str, seg_index: int, client: httpx.AsyncClient):
        async with semaphore:
            return await _synthesize_single_segment(
                client,
                seg_text,
                seg_index,
                message_id=message_id,
                model=model,
                base_url=base_url,
                api_key=api_key,
                voice_id=voice_id,
            )

    timeout = httpx.Timeout(60.0, connect=10.0, read=60.0, write=60.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(_worker(segment, idx, client))
            for idx, segment in enumerate(segments)
        ]

        for future in asyncio.as_completed(tasks):
            try:
                segment_data = await future
            except Exception as exc:
                logger.warning("[Voice] Segment synthesis failed for message=%s: %s", message_id, exc)
                continue

            seg_index = int(segment_data["segment_index"])
            collected[seg_index] = segment_data
            if on_segment_ready:
                try:
                    await on_segment_ready(segment_data)
                except Exception as callback_exc:
                    logger.warning("[Voice] on_segment_ready callback failed: %s", callback_exc)

    if not collected:
        return None

    ordered_segments = [collected[i] for i in sorted(collected.keys())]
    return {
        "voice_id": voice_id,
        "segments": ordered_segments,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

