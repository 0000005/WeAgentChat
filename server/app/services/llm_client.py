from typing import Optional

from agents import set_default_openai_api, set_default_openai_client
from openai import AsyncOpenAI


def set_agents_default_client(
    llm_config,
    *,
    timeout: Optional[float] = None,
    use_for_tracing: bool = True,
) -> AsyncOpenAI:
    client = AsyncOpenAI(
        base_url=llm_config.base_url,
        api_key=llm_config.api_key,
        timeout=timeout,
    )
    set_default_openai_client(client, use_for_tracing=use_for_tracing)
    set_default_openai_api("chat_completions")
    return client
