import asyncio
from .utils import exclude_special_kwargs, get_openai_async_client_instance
from ..env import LOG, CONFIG


async def openai_complete(
    model, prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    def _supports_sampling(model_name: str | None) -> bool:
        if not model_name:
            return True
        base = model_name.split("/", 1)[-1].lower()
        return not base.startswith("gpt-5")

    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)
    if not _supports_sampling(model):
        kwargs.pop("temperature", None)
        kwargs.pop("top_p", None)
        if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")

    openai_async_client = get_openai_async_client_instance()
    messages = []
    base_url = (CONFIG.llm_base_url or "").lower()
    is_gemini = "generativelanguage.googleapis.com" in base_url

    def _wrap_text_content(value):
        if isinstance(value, str):
            return [{"type": "text", "text": value}]
        return value

    if system_prompt:
        content = _wrap_text_content(system_prompt) if is_gemini else system_prompt
        messages.append({"role": "system", "content": content})
    if is_gemini:
        for msg in history_messages:
            content = _wrap_text_content(msg.get("content"))
            messages.append({**msg, "content": content})
    else:
        messages.extend(history_messages)
    user_content = _wrap_text_content(prompt) if is_gemini else prompt
    messages.append({"role": "user", "content": user_content})

    if is_gemini and "max_tokens" in kwargs:
        try:
            kwargs["max_tokens"] = max(int(kwargs["max_tokens"]), 64)
        except (TypeError, ValueError):
            pass

    last_error = None
    timeout = kwargs.pop("timeout", 300)
    if base_url:
        if "z.ai" in base_url or "bigmodel.cn" in base_url:
            timeout = max(timeout, 600)
    for attempt in range(3):
        try:
            response = await openai_async_client.chat.completions.create(
                model=model, messages=messages, timeout=timeout, **kwargs
            )
            break
        except Exception as exc:
            last_error = exc
            LOG.warning(
                f"OpenAI completion attempt {attempt + 1} failed: {exc}"
            )
            await asyncio.sleep(2 * (attempt + 1))
    else:
        raise last_error
    cached_tokens = getattr(response.usage.prompt_tokens_details, "cached_tokens", None)
    LOG.info(
        f"Cached {prompt_id} {model} {cached_tokens}/{response.usage.prompt_tokens}"
    )

    def _coerce_content(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                return value["text"]
            if "content" in value:
                return _coerce_content(value["content"])
            if "parts" in value:
                return _coerce_content(value["parts"])
            return ""
        if isinstance(value, list):
            parts = [_coerce_content(item) for item in value]
            return "".join([part for part in parts if part])
        return str(value)

    message = response.choices[0].message
    content = _coerce_content(getattr(message, "content", None))
    if not content:
        content = _coerce_content(getattr(message, "reasoning_content", None))
    if not content:
        content = _coerce_content(getattr(response.choices[0], "text", None))
    return content
