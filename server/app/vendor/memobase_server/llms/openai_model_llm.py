import asyncio
from .utils import exclude_special_kwargs, get_openai_async_client_instance
from ..env import LOG


async def openai_complete(
    model, prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    sp_args, kwargs = exclude_special_kwargs(kwargs)
    prompt_id = sp_args.get("prompt_id", None)

    openai_async_client = get_openai_async_client_instance()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(3):
        try:
            response = await openai_async_client.chat.completions.create(
                model=model, messages=messages, timeout=300, **kwargs
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
    return response.choices[0].message.content
