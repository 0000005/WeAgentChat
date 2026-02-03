import asyncio
from dataclasses import dataclass
import os

import httpx
import pytest
from agents import Agent, ModelSettings, Runner, set_default_openai_api, set_default_openai_client
from agents.items import ReasoningItem
from agents.stream_events import RunItemStreamEvent
from openai import AsyncOpenAI
from openai.types.responses import ResponseTextDeltaEvent
from openai.types.shared import Reasoning

from app.prompt import get_prompt
from app.services.llm_service import LLMService
from app.services import provider_rules
from app.services.reasoning_stream import extract_reasoning_delta


@dataclass(frozen=True)
class StreamCase:
    name: str
    base_url_env: str
    api_key_env: str
    model_env: str
    default_base_url: str
    default_model: str
    supports_reasoning: bool
    expects_reasoning_stream: bool
    use_litellm: bool = False


CASES = [
    StreamCase(
        name="openai_gpt_5_2",
        base_url_env="OPENAI_BASE_URL",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL_REASONING",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-5.2",
        supports_reasoning=True,
        expects_reasoning_stream=False,
    ),
    StreamCase(
        name="openai_gpt_4_1_nano",
        base_url_env="OPENAI_BASE_URL",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL_STANDARD",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4.1-nano",
        supports_reasoning=False,
        expects_reasoning_stream=False,
    ),
    StreamCase(
        name="gemini_3_flash_preview",
        base_url_env="GEMINI_BASE_URL",
        api_key_env="GEMINI_API_KEY",
        model_env="GEMINI_MODEL",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="models/gemini-3-flash-preview",
        supports_reasoning=True,
        expects_reasoning_stream=False,
        use_litellm=True,
    ),
    StreamCase(
        name="modelscope_qwen3_235b_a22b",
        base_url_env="MODELSCOPE_BASE_URL",
        api_key_env="MODELSCOPE_API_KEY",
        model_env="MODELSCOPE_MODEL",
        default_base_url="https://api-inference.modelscope.cn/v1",
        default_model="Qwen/Qwen3-235B-A22B-Instruct-2507",
        supports_reasoning=False,
        expects_reasoning_stream=False,
    ),
    StreamCase(
        name="minimax_m2_1",
        base_url_env="MINIMAX_BASE_URL",
        api_key_env="MINIMAX_API_KEY",
        model_env="MINIMAX_MODEL",
        default_base_url="https://api.minimaxi.com/v1",
        default_model="MiniMax-M2.1",
        supports_reasoning=False,
        expects_reasoning_stream=False,
    ),
    StreamCase(
        name="zhipu_glm_4_7",
        base_url_env="ZHIPU_BASE_URL",
        api_key_env="ZHIPU_API_KEY",
        model_env="ZHIPU_MODEL",
        default_base_url="https://api.z.ai/api/coding/paas/v4/",
        default_model="glm-4.7",
        supports_reasoning=True,
        expects_reasoning_stream=True,
    ),
    StreamCase(
        name="deepseek_chat",
        base_url_env="DEEPSEEK_BASE_URL",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",
        default_base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        supports_reasoning=False,
        expects_reasoning_stream=False,
    ),
]


def _supports_sampling(model_name: str) -> bool:
    return not model_name.split("/", 1)[-1].lower().startswith("gpt-5")


def _normalize_base_url(case: StreamCase, base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if case.use_litellm:
        if trimmed.endswith("/openai"):
            return trimmed[: -len("/openai")]
        return trimmed
    if case.name.startswith("gemini"):
        if not trimmed.endswith("/openai"):
            return f"{trimmed}/openai"
    return base_url


def _resolve_case(case: StreamCase) -> tuple[str, str, str]:
    base_url = os.getenv(case.base_url_env) or case.default_base_url
    api_key = os.getenv(case.api_key_env)
    model_name = os.getenv(case.model_env) or case.default_model

    if not api_key:
        pytest.skip(f"Missing env for {case.name}: {case.api_key_env}")

    base_url = _normalize_base_url(case, base_url)
    if case.use_litellm and case.name.startswith("gemini"):
        normalized_model = provider_rules.normalize_gemini_model_name(model_name)
    else:
        normalized_model = LLMService.normalize_model_name(model_name) or model_name
    return base_url, api_key, normalized_model


async def _run_stream_probe(
    base_url: str,
    api_key: str,
    model_name: str,
    *,
    enable_thinking: bool,
    supports_reasoning: bool,
    use_litellm: bool,
) -> tuple[bool, bool, set[str]]:
    os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")


    async with httpx.AsyncClient(timeout=90.0) as http_client:
        openai_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
        )
        set_default_openai_client(openai_client, use_for_tracing=False)
        set_default_openai_api("chat_completions")

        model_settings_kwargs = {}
        if _supports_sampling(model_name):
            if not (use_litellm and model_name.startswith("gemini/")):
                model_settings_kwargs["temperature"] = 0
                model_settings_kwargs["top_p"] = 1
        if supports_reasoning:
            model_settings_kwargs["reasoning"] = Reasoning(effort="low" if enable_thinking else "none")

        if use_litellm:
            from agents.extensions.models.litellm_model import LitellmModel

            agent_model = LitellmModel(
                model=model_name,
                base_url=base_url,
                api_key=api_key,
            )
        else:
            agent_model = model_name

        agent = Agent(
            name="ReasoningProbe",
            instructions="",
            model=agent_model,
            model_settings=ModelSettings(**model_settings_kwargs),
        )

        prompt = get_prompt("tests/llm_test_reasoning_user_message.txt").strip()
        result = Runner.run_streamed(agent, [{"role": "user", "content": prompt}])

        raw_event_types: set[str] = set()
        reasoning_seen = False
        text_seen = False
        full_text = ""

        async for event in result.stream_events():
            if isinstance(event, RunItemStreamEvent) and event.name == "reasoning_item_created":
                if isinstance(event.item, ReasoningItem):
                    reasoning_seen = True
                continue

            if event.type == "raw_response_event":
                raw_event_types.add(type(event.data).__name__)
                reasoning_delta = extract_reasoning_delta(event.data)
                if reasoning_delta:
                    reasoning_seen = True

            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                if event.data.delta:
                    text_seen = True
                    full_text += event.data.delta


        text_has_think = "<think>" in full_text.lower()
        reasoning_seen = reasoning_seen or text_has_think
        return reasoning_seen, text_seen, raw_event_types


@pytest.mark.parametrize("case", [c for c in CASES if c.expects_reasoning_stream], ids=lambda c: c.name)
def test_reasoning_stream_enabled(case: StreamCase):
    base_url, api_key, model_name = _resolve_case(case)
    reasoning_seen, text_seen, raw_event_types = asyncio.run(
        _run_stream_probe(
            base_url,
            api_key,
            model_name,
            enable_thinking=True,
            supports_reasoning=case.supports_reasoning,
            use_litellm=case.use_litellm,
        )
    )
    assert text_seen is True
    assert reasoning_seen is True, f"{case.name} reasoning missing, events={sorted(raw_event_types)}"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_reasoning_stream_disabled(case: StreamCase):
    base_url, api_key, model_name = _resolve_case(case)
    reasoning_seen, text_seen, raw_event_types = asyncio.run(
        _run_stream_probe(
            base_url,
            api_key,
            model_name,
            enable_thinking=False,
            supports_reasoning=case.supports_reasoning,
            use_litellm=case.use_litellm,
        )
    )
    assert text_seen is True, f"{case.name} no text output, events={sorted(raw_event_types)}"
