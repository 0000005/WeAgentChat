from typing import Optional


def _get_provider(llm_config) -> str:
    return (getattr(llm_config, "provider", "") or "").lower()


def _get_base_url(llm_config) -> str:
    return (getattr(llm_config, "base_url", "") or "").lower()


def is_gemini_model(llm_config, model_name: Optional[str]) -> bool:
    provider = _get_provider(llm_config)
    base_url = _get_base_url(llm_config)
    if provider == "gemini":
        return True
    if "generativelanguage.googleapis.com" in base_url:
        return True
    return "gemini" in (model_name or "").lower()


def is_deepseek_model(llm_config, model_name: Optional[str]) -> bool:
    provider = _get_provider(llm_config)
    base_url = _get_base_url(llm_config)
    if provider == "deepseek":
        return True
    if "deepseek" in base_url:
        return True
    return "deepseek" in (model_name or "").lower()


def normalize_gemini_model_name(model_name: Optional[str]) -> str:
    raw = (model_name or "").strip()
    if not raw:
        return "gemini/gemini-3-pro-preview"
    if "/" in raw:
        prefix, rest = raw.split("/", 1)
        if prefix in ("gemini", "vertex_ai", "google"):
            return raw
        return f"gemini/{rest}"
    return f"gemini/{raw}"


def normalize_gemini_base_url(base_url: Optional[str]) -> Optional[str]:
    raw = (base_url or "").strip()
    if not raw:
        return None
    trimmed = raw.rstrip("/")
    if trimmed.endswith("/openai"):
        return trimmed[: -len("/openai")]
    return raw


def should_use_litellm(llm_config, model_name: Optional[str]) -> bool:
    return is_gemini_model(llm_config, model_name)


def supports_reasoning_effort(llm_config) -> bool:
    provider = _get_provider(llm_config)
    base_url = _get_base_url(llm_config)
    if provider in ("openai", "deepseek", "gemini"):
        return True
    if provider == "openai_compatible":
        if "openai.com" in base_url or "deepseek" in base_url:
            return True
        return False
    if is_gemini_model(llm_config, None):
        return True
    if "deepseek" in base_url:
        return True
    return False


def get_reasoning_effort(
    llm_config,
    model_name: Optional[str],
    enable_thinking: bool,
) -> str:
    if not enable_thinking:
        return "none"
    if is_gemini_model(llm_config, model_name):
        return "low"
    return "low"


def needs_gemini_thought_signature(llm_config, model_name: Optional[str]) -> bool:
    return is_gemini_model(llm_config, model_name)


def needs_deepseek_reasoning_item(llm_config, model_name: Optional[str]) -> bool:
    return is_deepseek_model(llm_config, model_name)


def supports_json_mode(llm_config, model_name: Optional[str] = None) -> bool:
    provider = _get_provider(llm_config)
    base_url = _get_base_url(llm_config)
    if provider in ("openai", "deepseek"):
        return True
    if provider == "openai_compatible":
        if "openai.com" in base_url or "deepseek" in base_url:
            return True
        return False
    if "openai.com" in base_url or "deepseek" in base_url:
        return True
    if is_gemini_model(llm_config, model_name):
        return False
    return False


def json_mode_response_format(llm_config, model_name: Optional[str] = None) -> Optional[dict]:
    if supports_json_mode(llm_config, model_name):
        return {"response_format": {"type": "json_object"}}
    return None


def is_json_mode_unsupported_error(error: Exception) -> bool:
    message = str(error).lower()
    if "response_format" in message and ("not supported" in message or "unsupported" in message):
        return True
    if "response_format" in message and ("invalid" in message or "unknown" in message):
        return True
    if "json" in message and "response_format" in message:
        return True
    status_code = getattr(error, "status_code", None)
    if status_code == 400 and "response_format" in message:
        return True
    return False
