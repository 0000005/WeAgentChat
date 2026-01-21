import asyncio
import os
import statistics
import time

import httpx
import pytest
from agents import Agent, ModelSettings, Runner, set_default_openai_api, set_default_openai_client
from openai import AsyncOpenAI

BASE_URL = os.getenv("LATENCY_TEST_BASE_URL") or os.getenv("MEMOBASE_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("LATENCY_TEST_API_KEY") or os.getenv("MEMOBASE_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("LATENCY_TEST_MODEL") or os.getenv("MEMOBASE_BEST_LLM_MODEL") or "gpt-4o-mini"
RUNS = int(os.getenv("LATENCY_TEST_RUNS", "10"))

if BASE_URL:
    BASE_URL = BASE_URL.rstrip("/") + "/"
CHAT_COMPLETIONS_URL = os.getenv("LATENCY_TEST_CHAT_URL") or (f"{BASE_URL}chat/completions" if BASE_URL else None)


async def _measure_agent_latency() -> list[float]:
    if "OPENAI_AGENTS_DISABLE_TRACING" not in os.environ:
        os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "0"
    max_retries_env = os.getenv("OPENAI_MAX_RETRIES")
    openai_kwargs: dict[str, object] = {}
    if max_retries_env is not None:
        openai_kwargs["max_retries"] = int(max_retries_env)
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        openai_client = AsyncOpenAI(
            base_url=BASE_URL,
            api_key=API_KEY,
            http_client=http_client,
            **openai_kwargs,
        )
        set_default_openai_client(openai_client, use_for_tracing=False)
        set_default_openai_api("chat_completions")

        agent = Agent(
            name="LatencyBenchAgent",
            instructions="",
            model=MODEL_NAME,
            model_settings=ModelSettings(max_tokens=16, temperature=0),
        )

        timings: list[float] = []
        for _ in range(RUNS):
            start = time.perf_counter()
            result = await Runner.run(agent, [{"role": "user", "content": "hello world"}])
            _ = result.final_output
            timings.append(time.perf_counter() - start)
        return timings


async def _measure_http_latency() -> list[float]:
    headers = {"Authorization": f"Bearer {API_KEY}"}
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "hello world"}],
        "max_tokens": 16,
        "temperature": 0,
    }

    timings: list[float] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for _ in range(RUNS):
            start = time.perf_counter()
            response = await client.post(CHAT_COMPLETIONS_URL, headers=headers, json=payload)
            response.raise_for_status()
            _ = response.json()
            timings.append(time.perf_counter() - start)
    return timings


def _format_stats(name: str, timings: list[float]) -> str:
    avg = statistics.mean(timings)
    p50 = statistics.median(timings)
    return f"{name}: avg={avg:.3f}s, p50={p50:.3f}s, runs={len(timings)}"


def test_openai_agent_vs_http_latency():
    if not API_KEY or not BASE_URL or not CHAT_COMPLETIONS_URL:
        pytest.skip("Missing latency test configuration (API_KEY/BASE_URL).")
    agent_timings = asyncio.run(_measure_agent_latency())
    http_timings = asyncio.run(_measure_http_latency())

    print(_format_stats("openai-agents", agent_timings))
    print(_format_stats("http", http_timings))

    assert len(agent_timings) == RUNS
    assert len(http_timings) == RUNS
