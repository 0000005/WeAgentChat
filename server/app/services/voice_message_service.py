import asyncio
import json
import logging
import math
import os
import re
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from agents import Agent, ModelSettings, RunConfig, Runner
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import Message
from app.models.friend import Friend
from app.models.group import GroupMessage
from app.prompt import get_prompt
from app.services import provider_rules
from app.services.llm_client import set_agents_default_client
from app.services.llm_service import llm_service
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
DEFAULT_TTS_MODEL = "qwen3-tts-instruct-flash"
VOICE_ENDPOINT = "/services/aigc/multimodal-generation/generation"
MAX_TTS_PARALLELISM = 2
MAX_TTS_SEGMENT_CHARS = 300
MAX_EMOTION_CONTEXT_MESSAGES = 12
MAX_EMOTION_CONTEXT_CHARS = 1200
MAX_EMOTION_REPLY_CHARS = 800


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


def _split_segment_by_period(text: str, max_chars: int = MAX_TTS_SEGMENT_CHARS) -> List[str]:
    compact = (text or "").strip()
    if not compact:
        return []
    if len(compact) <= max_chars:
        return [compact]

    raw_parts = compact.split("。")
    parts: List[str] = []
    for idx, raw_part in enumerate(raw_parts):
        part = raw_part.strip()
        if not part:
            continue
        # 除最后一段外补回句号，尽量保持原文语气停顿。
        if idx < len(raw_parts) - 1:
            part = f"{part}。"
        parts.append(part)

    merged: List[str] = []
    current = ""
    for part in parts:
        if not current:
            current = part
            continue
        if len(current) + len(part) <= max_chars:
            current += part
        else:
            merged.append(current)
            current = part
    if current:
        merged.append(current)

    # 兜底：若单句本身超过上限，按长度硬切分，确保每片段 <= max_chars。
    result: List[str] = []
    for chunk in merged:
        if len(chunk) <= max_chars:
            result.append(chunk)
            continue
        for i in range(0, len(chunk), max_chars):
            result.append(chunk[i : i + max_chars])
    return result


def _normalize_base_url(base_url: Optional[str]) -> str:
    normalized = (base_url or DEFAULT_DASHSCOPE_BASE_URL).strip()
    if not normalized:
        normalized = DEFAULT_DASHSCOPE_BASE_URL
    return normalized.rstrip("/")


def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    normalized = str(model_name).strip().lower()
    if not normalized:
        return ""
    # 兼容 provider/namespace/model 等多级前缀写法，统一取最后一段模型名。
    return normalized.split("/")[-1]


def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")


def _supports_tts_instructions(model_name: Optional[str]) -> bool:
    base_name = _model_base_name(model_name)
    if base_name.startswith("qwen3-tts-instruct-flash"):
        return True
    # 兜底：兼容异常命名格式，避免误判导致情绪增强静默失效。
    return "qwen3-tts-instruct-flash" in str(model_name or "").strip().lower()


def _strip_message_tags(content: Optional[str]) -> str:
    if not content:
        return ""
    parts = re.findall(r"<message>(.*?)</message>", content, re.DOTALL)
    if parts:
        return " ".join(part.strip() for part in parts if part and part.strip())
    return re.sub(r"</?message>", "", content).strip()


def _compact_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _clip_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _strip_think_blocks(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = str(text)
    # 清理常见推理块，避免把思维链注入到 TTS instructions。
    cleaned = re.sub(r"(?is)<think>[\s\S]*?</think>", " ", cleaned)
    cleaned = re.sub(r"(?is)<thinking>[\s\S]*?</thinking>", " ", cleaned)
    # 兜底移除残留标签（例如模型输出了不完整标签）。
    cleaned = re.sub(r"(?is)</?think>", " ", cleaned)
    cleaned = re.sub(r"(?is)</?thinking>", " ", cleaned)
    return cleaned


def _mask_api_key(api_key: Optional[str]) -> str:
    if not api_key:
        return ""
    value = str(api_key)
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _http_response_error_summary(exc: httpx.HTTPStatusError) -> Dict[str, Any]:
    response = exc.response
    request = exc.request
    headers = response.headers
    request_id = (
        headers.get("x-dashscope-request-id")
        or headers.get("x-request-id")
        or headers.get("request-id")
        or headers.get("x-trace-id")
        or ""
    )
    try:
        raw_body = json.dumps(response.json(), ensure_ascii=False)
    except Exception:
        raw_body = response.text or ""

    return {
        "status_code": response.status_code,
        "method": request.method,
        "url": str(request.url),
        "request_id": request_id,
        "response_body": _clip_text(_compact_text(raw_body), 2000),
    }


def _build_tts_request_debug(
    *,
    endpoint: str,
    model: str,
    voice_id: str,
    segment_text: str,
    emotion_instruction: Optional[str],
    api_key: str,
) -> Dict[str, Any]:
    return {
        "endpoint": endpoint,
        "model": model,
        "voice": voice_id,
        "language_type": "Chinese",
        "text_len": len(segment_text or ""),
        "text_preview": _clip_text(_compact_text(segment_text or ""), 120),
        "has_instructions": bool(emotion_instruction),
        "instructions_len": len(emotion_instruction or ""),
        "optimize_instructions": bool(emotion_instruction),
        "api_key_masked": _mask_api_key(api_key),
    }


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


def resolve_voice_runtime_config(db: Session) -> Optional[Dict[str, Any]]:
    api_key = str(SettingsService.get_setting(db, "voice", "api_key", "") or "").strip()
    if not api_key:
        return None

    model = str(SettingsService.get_setting(db, "voice", "tts_model", DEFAULT_TTS_MODEL) or DEFAULT_TTS_MODEL).strip()
    if not model:
        model = DEFAULT_TTS_MODEL

    base_url_raw = SettingsService.get_setting(db, "voice", "base_url", None)
    base_url = _normalize_base_url(str(base_url_raw) if isinstance(base_url_raw, str) else None)

    default_voice_id = str(SettingsService.get_setting(db, "voice", "default_voice_id", "") or "").strip()
    emotion_enhance_enabled = bool(
        SettingsService.get_setting(db, "voice", "emotion_enhance_enabled", False)
    )
    emotion_llm_config_id = SettingsService.get_setting(db, "voice", "emotion_llm_config_id", "")

    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "default_voice_id": default_voice_id,
        "emotion_enhance_enabled": emotion_enhance_enabled,
        "emotion_llm_config_id": emotion_llm_config_id,
    }


def _resolve_emotion_llm_config(db: Session, configured_value: Any):
    configured_id: Optional[int] = None
    if isinstance(configured_value, int):
        configured_id = configured_value
    elif isinstance(configured_value, str):
        stripped = configured_value.strip()
        if stripped:
            try:
                configured_id = int(stripped)
            except ValueError:
                logger.warning(
                    "[Voice] Invalid emotion_llm_config_id setting value: %s",
                    configured_value,
                )

    if configured_id is not None:
        config = llm_service.get_config_by_id(db, configured_id)
        if config:
            return config
        logger.warning(
            "[Voice] Emotion LLM config %s not found, fallback to active chat model.",
            configured_id,
        )

    return llm_service.get_active_config(db)


def _build_single_chat_context(db: Session, message: Message) -> str:
    history = (
        db.query(Message)
        .filter(
            Message.session_id == message.session_id,
            Message.deleted == False,
            Message.id < message.id,
        )
        .order_by(Message.id.desc())
        .limit(MAX_EMOTION_CONTEXT_MESSAGES)
        .all()
    )
    history.reverse()
    lines: List[str] = []
    for item in history:
        role = (item.role or "").lower()
        if role == "user":
            label = "用户"
        elif role == "assistant":
            label = "好友"
        else:
            label = role or "消息"
        content = _compact_text(_strip_message_tags(item.content))
        if content:
            lines.append(f"{label}: {content}")
    context = "\n".join(lines)
    return _clip_text(context, MAX_EMOTION_CONTEXT_CHARS)


def _build_group_chat_context(db: Session, message: GroupMessage) -> str:
    history = (
        db.query(GroupMessage)
        .filter(
            GroupMessage.session_id == message.session_id,
            GroupMessage.id < message.id,
        )
        .order_by(GroupMessage.id.desc())
        .limit(MAX_EMOTION_CONTEXT_MESSAGES)
        .all()
    )
    history.reverse()

    friend_ids: List[int] = []
    for item in history:
        if item.sender_type != "friend":
            continue
        try:
            friend_ids.append(int(item.sender_id))
        except (TypeError, ValueError):
            continue
    friend_name_map: Dict[int, str] = {}
    if friend_ids:
        friends = db.query(Friend).filter(Friend.id.in_(friend_ids)).all()
        friend_name_map = {f.id: f.name for f in friends}

    lines: List[str] = []
    for item in history:
        sender_type = (item.sender_type or "").lower()
        if sender_type == "user":
            label = "用户"
        elif sender_type == "friend":
            try:
                fid = int(item.sender_id)
            except (TypeError, ValueError):
                fid = None
            label = f"群友({friend_name_map.get(fid, item.sender_id)})"
        else:
            label = "系统"
        content = _compact_text(_strip_message_tags(item.content))
        if content:
            lines.append(f"{label}: {content}")
    context = "\n".join(lines)
    return _clip_text(context, MAX_EMOTION_CONTEXT_CHARS)


def _build_tts_emotion_context(db: Session, message_id: int) -> str:
    return _build_tts_emotion_context_with_scope(db, message_id, None)


def _build_tts_emotion_context_with_scope(
    db: Session,
    message_id: int,
    message_scope: Optional[str],
) -> str:
    scope = (message_scope or "").strip().lower()
    if scope == "single":
        single_message = db.query(Message).filter(Message.id == message_id).first()
        return _build_single_chat_context(db, single_message) if single_message else ""
    if scope == "group":
        group_message = db.query(GroupMessage).filter(GroupMessage.id == message_id).first()
        return _build_group_chat_context(db, group_message) if group_message else ""

    # 兼容旧调用：未知 scope 时做双表探测。
    single_message = db.query(Message).filter(Message.id == message_id).first()
    if single_message:
        return _build_single_chat_context(db, single_message)

    group_message = db.query(GroupMessage).filter(GroupMessage.id == message_id).first()
    if group_message:
        return _build_group_chat_context(db, group_message)

    return ""


def _extract_result_text(result: Any) -> str:
    final_output = getattr(result, "final_output", None)
    if isinstance(final_output, str):
        return final_output

    if final_output is not None:
        text = getattr(final_output, "text", None)
        if text:
            return str(text)
        if isinstance(final_output, dict):
            dict_text = final_output.get("text") or final_output.get("content")
            if dict_text:
                return str(dict_text)
        return str(final_output)

    parts: List[str] = []
    for item in (getattr(result, "new_items", None) or []):
        raw_item = getattr(item, "raw_item", None)
        content = getattr(raw_item, "content", None)
        if not content:
            continue
        if isinstance(content, str):
            parts.append(content)
            continue
        for part in content:
            if isinstance(part, dict):
                text = part.get("text")
            else:
                text = getattr(part, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts)


async def _generate_tts_emotion_instruction(
    db: Session,
    *,
    content: str,
    message_id: int,
    message_scope: Optional[str],
    runtime_config: Dict[str, Any],
) -> Optional[str]:
    if not bool(runtime_config.get("emotion_enhance_enabled")):
        logger.info("[Voice] Emotion enhancement disabled for message=%s.", message_id)
        return None
    tts_model = runtime_config.get("model")
    if not _supports_tts_instructions(tts_model):
        logger.info(
            "[Voice] Emotion enhancement skipped for message=%s: tts_model=%s does not support instructions.",
            message_id,
            tts_model,
        )
        return None
    logger.info(
        "[Voice] Emotion enhancement started for message=%s tts_model=%s emotion_llm_config_id=%s",
        message_id,
        tts_model,
        runtime_config.get("emotion_llm_config_id"),
    )

    llm_config = _resolve_emotion_llm_config(db, runtime_config.get("emotion_llm_config_id"))
    if not llm_config:
        logger.info("[Voice] Skip emotion enhancement: no LLM config available.")
        return None

    raw_model_name = llm_config.model_name
    if not raw_model_name:
        logger.info("[Voice] Skip emotion enhancement: empty model_name.")
        return None

    reply_text = _clip_text(_compact_text(_strip_message_tags(content)), MAX_EMOTION_REPLY_CHARS)
    if not reply_text:
        return None
    context_text = _build_tts_emotion_context_with_scope(db, message_id, message_scope) or "(暂无上下文)"

    try:
        prompt_template = get_prompt("chat/tts-emotion-instructions.txt").strip()
    except Exception as exc:
        logger.warning("[Voice] Skip emotion enhancement: prompt load failed: %s", exc)
        return None

    instructions = (
        prompt_template.replace("{{chat_context}}", context_text)
        .replace("{{reply_text}}", reply_text)
    )

    try:
        set_agents_default_client(llm_config, use_for_tracing=True)
        model_name = llm_service.normalize_model_name(raw_model_name)
        use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
        model_settings_kwargs: Dict[str, Any] = {}
        if _supports_sampling(model_name):
            temperature = 0.4
            if use_litellm and provider_rules.is_gemini_model(llm_config, raw_model_name):
                temperature = 1.0
            model_settings_kwargs["temperature"] = temperature
            model_settings_kwargs["top_p"] = 0.9
        model_settings = ModelSettings(**model_settings_kwargs)

        if use_litellm:
            from agents.extensions.models.litellm_model import LitellmModel

            gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
            gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
            agent_model = LitellmModel(
                model=gemini_model_name,
                base_url=gemini_base_url,
                api_key=llm_config.api_key,
            )
        else:
            agent_model = model_name

        agent = Agent(
            name="TTSEmotionInstructionGenerator",
            instructions=instructions,
            model=agent_model,
            model_settings=model_settings,
        )

        result = await asyncio.wait_for(
            Runner.run(
                agent,
                "",
                run_config=RunConfig(trace_include_sensitive_data=True),
            ),
            timeout=20.0,
        )
        raw_emotion_instruction = _extract_result_text(result)
        raw_compact_instruction = _compact_text(raw_emotion_instruction)
        emotion_instruction = _compact_text(_strip_think_blocks(raw_emotion_instruction))
        if not emotion_instruction:
            logger.info("[Voice] Emotion enhancement generated empty instruction.")
            return None
        if raw_compact_instruction != emotion_instruction:
            logger.info(
                "[Voice] Removed reasoning content from emotion instructions for message=%s.",
                message_id,
            )
        # 保护性截断，避免极端情况下 instructions 超长导致 TTS 请求失败。
        emotion_instruction = _clip_text(emotion_instruction, 240)
        logger.info(
            "[Voice] Emotion enhancement enabled for message=%s using llm_config=%s",
            message_id,
            llm_config.id,
        )
        logger.info(
            "[Voice] Emotion instructions for message=%s: %s",
            message_id,
            emotion_instruction,
        )
        return emotion_instruction
    except Exception as exc:
        logger.warning(
            "[Voice] Emotion enhancement failed for message=%s: %s",
            message_id,
            exc,
        )
        return None


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
    emotion_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    endpoint = f"{base_url}{VOICE_ENDPOINT}"
    request_debug = _build_tts_request_debug(
        endpoint=endpoint,
        model=model,
        voice_id=voice_id,
        segment_text=segment_text,
        emotion_instruction=emotion_instruction,
        api_key=api_key,
    )
    input_payload: Dict[str, Any] = {
        "text": segment_text,
        "voice": voice_id,
        "language_type": "Chinese",
    }
    if emotion_instruction:
        input_payload["instructions"] = emotion_instruction
        input_payload["optimize_instructions"] = True

    request_body = {
        "model": model,
        "input": input_payload,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = await client.post(endpoint, json=request_body, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        err_summary = _http_response_error_summary(exc)
        logger.warning(
            "[Voice] TTS request failed for message=%s segment=%s status=%s request_id=%s request=%s response=%s",
            message_id,
            segment_index,
            err_summary["status_code"],
            err_summary["request_id"],
            request_debug,
            err_summary["response_body"],
        )
        raise
    except httpx.RequestError as exc:
        logger.warning(
            "[Voice] TTS request network error for message=%s segment=%s type=%s request=%s error=%s",
            message_id,
            segment_index,
            type(exc).__name__,
            request_debug,
            exc,
        )
        raise

    payload = response.json()

    remote_audio_url = _extract_audio_url(payload)
    if not remote_audio_url:
        payload_preview = _clip_text(_compact_text(json.dumps(payload, ensure_ascii=False)), 2000)
        raise ValueError(f"TTS 响应中未找到 audio url: payload={payload_preview}")

    try:
        audio_resp = await client.get(remote_audio_url)
        audio_resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        err_summary = _http_response_error_summary(exc)
        logger.warning(
            "[Voice] Audio download failed for message=%s segment=%s status=%s request_id=%s remote_url=%s response=%s",
            message_id,
            segment_index,
            err_summary["status_code"],
            err_summary["request_id"],
            remote_audio_url,
            err_summary["response_body"],
        )
        raise
    except httpx.RequestError as exc:
        logger.warning(
            "[Voice] Audio download network error for message=%s segment=%s type=%s remote_url=%s error=%s",
            message_id,
            segment_index,
            type(exc).__name__,
            remote_audio_url,
            exc,
        )
        raise

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
    message_scope: Optional[str] = None,
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

    raw_segments = parse_message_segments(content)
    segments = []
    for seg in raw_segments:
        segments.extend(_split_segment_by_period(seg, max_chars=MAX_TTS_SEGMENT_CHARS))
    if not segments:
        return None
    if len(segments) != len(raw_segments):
        logger.info(
            "[Voice] Segment split applied for message=%s raw_segments=%s normalized_segments=%s max_chars=%s",
            message_id,
            len(raw_segments),
            len(segments),
            MAX_TTS_SEGMENT_CHARS,
        )

    model = runtime_config["model"]
    base_url = runtime_config["base_url"]
    api_key = runtime_config["api_key"]
    emotion_instruction = await _generate_tts_emotion_instruction(
        db,
        content=content,
        message_id=message_id,
        message_scope=message_scope,
        runtime_config=runtime_config,
    )
    if bool(runtime_config.get("emotion_enhance_enabled")):
        if emotion_instruction:
            logger.info(
                "[Voice] Emotion instruction applied for message=%s (length=%s).",
                message_id,
                len(emotion_instruction),
            )
        else:
            logger.info("[Voice] Emotion instruction not generated for message=%s.", message_id)

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
                emotion_instruction=emotion_instruction,
            )

    timeout = httpx.Timeout(60.0, connect=10.0, read=60.0, write=60.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        tasks = [
            asyncio.create_task(_worker(segment, idx, client), name=f"voice-seg-{idx}")
            for idx, segment in enumerate(segments)
        ]

        for future in asyncio.as_completed(tasks):
            try:
                segment_data = await future
            except Exception as exc:
                task_name = future.get_name() if hasattr(future, "get_name") else "voice-seg-unknown"
                logger.warning(
                    "[Voice] Segment synthesis failed for message=%s task=%s type=%s error=%s",
                    message_id,
                    task_name,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
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
