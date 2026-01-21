import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.session import SessionLocal
from app.models.llm import LLMConfig
from app.services.memo.constants import DEFAULT_SPACE_ID, DEFAULT_USER_ID
from app.services.recall_service import RecallService
from agents import Agent, Runner
from agents.items import ToolCallItem, ToolCallOutputItem


pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_recall_service_returns_events_from_seed_data():
    db = SessionLocal()
    try:
        llm_config = (
            db.query(LLMConfig)
            .filter(LLMConfig.deleted == False)
            .order_by(LLMConfig.id.desc())
            .first()
        )
        if not llm_config or not llm_config.api_key:
            pytest.skip("LLMConfig.api_key missing; recall agent cannot run.")

        seed_path = Path("dev-docs/scripts/seed_memories.py")
        seed_source = seed_path.read_text(encoding="utf-8-sig")
        seed_module = ast.parse(seed_source)
        life_events: list[str] = []
        for node in ast.walk(seed_module):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "life_events":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    life_events.append(elt.value)
        assert life_events, "Failed to extract life_events from seed_memories.py"

        dummy_agent = Agent(name="RecallAgent", instructions="test", model="test")
        call_id = "call_seed_1"
        call_id_2 = "call_seed_2"
        tool_call_item = ToolCallItem(
            agent=dummy_agent,
            raw_item={
                "type": "function_call",
                "name": "recall_memory",
                "call_id": call_id,
                "arguments": '{"query":"失眠"}',
            },
        )
        tool_call_item_2 = ToolCallItem(
            agent=dummy_agent,
            raw_item={
                "type": "function_call",
                "name": "recall_memory",
                "call_id": call_id_2,
                "arguments": '{"query":"睡眠质量"}',
            },
        )
        tool_output_item = ToolCallOutputItem(
            agent=dummy_agent,
            raw_item={
                "type": "function_call_output",
                "call_id": call_id,
                "output": "",
            },
            output={
                "events": [
                    {"date": None, "content": life_events[0], "similarity": 0.9},
                    {"date": None, "content": life_events[1], "similarity": 0.8},
                ]
            },
        )
        tool_output_item_2 = ToolCallOutputItem(
            agent=dummy_agent,
            raw_item={
                "type": "function_call_output",
                "call_id": call_id_2,
                "output": "",
            },
            output={
                "events": [
                    {"date": None, "content": life_events[2], "similarity": 0.85},
                ]
            },
        )

        async def fake_run(_agent, _messages, **_kwargs):
            return SimpleNamespace(
                new_items=[
                    tool_call_item,
                    tool_output_item,
                    tool_call_item_2,
                    tool_output_item_2,
                ]
            )

        original_run = Runner.run
        Runner.run = fake_run  # type: ignore[assignment]
        try:
            messages = [
                {"role": "user", "content": "最近睡眠不好，总是失眠，有没有什么建议？"}
            ]
            result = await RecallService.perform_recall(
                db=db,
                user_id=DEFAULT_USER_ID,
                space_id=DEFAULT_SPACE_ID,
                messages=messages,
                friend_id=2,
            )
        finally:
            Runner.run = original_run  # type: ignore[assignment]

        assert isinstance(result, dict)
        assert "injected_messages" in result
        injected = result["injected_messages"]
        assert len(injected) == 2
        tool_call, tool_output = injected
        assert tool_call.get("type") == "function_call"
        assert tool_call.get("name") == "recall_memory"
        assert tool_output.get("type") == "function_call_output"
        assert tool_output.get("call_id") == tool_call.get("call_id")
        assert tool_call.get("call_id") == call_id_2

        output_text = tool_output.get("output") or ""
        assert "events" in output_text
        assert life_events[0] in output_text
        assert life_events[1] in output_text
        assert life_events[2] in output_text
    finally:
        db.close()
