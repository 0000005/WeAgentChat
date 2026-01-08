import json
import logging
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.items import ReasoningItem, ToolCallItem, ToolCallOutputItem
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.models.llm import LLMConfig
from app.services.memo.bridge import MemoService
from app.services.settings_service import SettingsService
from app.prompt import get_prompt


logger = logging.getLogger(__name__)
prompt_logger = logging.getLogger("prompt_trace")


class RecallService:
    @staticmethod
    def _normalize_messages(messages: Iterable[Any]) -> List[Dict[str, str]]:
        normalized: List[Dict[str, str]] = []
        for message in messages:
            if isinstance(message, dict):
                role = message.get("role")
                content = message.get("content")
            else:
                role = getattr(message, "role", None)
                content = getattr(message, "content", None)
            if not role or content is None:
                continue
            normalized.append({"role": role, "content": content})
        return normalized

    @staticmethod
    def _extract_reasoning_text(item: ReasoningItem) -> str:
        raw = item.raw_item
        parts = []
        summary = getattr(raw, "summary", None)
        if summary:
            for entry in summary:
                text = getattr(entry, "text", None)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _extract_tool_call(item: ToolCallItem) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        raw = item.raw_item
        if isinstance(raw, dict):
            return raw.get("name"), raw.get("call_id"), raw.get("arguments")
        name = getattr(raw, "name", None)
        call_id = getattr(raw, "call_id", None)
        arguments = getattr(raw, "arguments", None)
        return name, call_id, arguments

    @staticmethod
    def _merge_events(outputs: Iterable[Dict[str, Any]], max_events: int) -> List[Dict[str, Any]]:
        merged: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]] = {}
        for output in outputs:
            for event in output.get("events", []) or []:
                if not isinstance(event, dict):
                    continue
                key = (event.get("date"), event.get("content"))
                existing = merged.get(key)
                if not existing:
                    merged[key] = event
                    continue
                existing_similarity = existing.get("similarity") or 0
                new_similarity = event.get("similarity") or 0
                if new_similarity > existing_similarity:
                    merged[key] = event
        merged_events = list(merged.values())
        merged_events.sort(key=lambda item: item.get("similarity") or 0, reverse=True)
        if max_events > 0:
            return merged_events[:max_events]
        return merged_events

    @classmethod
    async def perform_recall(
        cls,
        db: Session,
        user_id: str,
        space_id: str,
        messages: Iterable[Any],
        friend_id: int,
    ) -> Dict[str, Any]:
        """
        执行记忆召回。
        返回:
            {
                "injected_messages": [mock_tool_call, mock_tool_result],
                "footprints": [
                    {"type": "thinking", "content": "..."},
                    {"type": "tool_call", "name": "...", "arguments": "..."},
                    {"type": "tool_result", "name": "...", "result": "..."},
                    ...
                ]
            }
        """
        llm_config = (
            db.query(LLMConfig)
            .filter(LLMConfig.deleted == False)
            .order_by(LLMConfig.id.desc())
            .first()
        )
        if not llm_config:
            raise Exception("LLM configuration not found in database")

        search_rounds = SettingsService.get_setting(db, "memory", "search_rounds", 3)
        event_topk = SettingsService.get_setting(db, "memory", "event_topk", 5)
        threshold = SettingsService.get_setting(db, "memory", "similarity_threshold", 0.5)

        tool_description = get_prompt("recall/recall_tool_description.txt").strip()

        @function_tool(
            name_override="recall_memory",
            description_override=tool_description,
        )
        async def tool_recall(query: str) -> Dict[str, Any]:
            return await MemoService.recall_memory(
                user_id=user_id,
                space_id=space_id,
                query=query,
                friend_id=friend_id,
                topk_event=event_topk,
                threshold=threshold,
            )

        client = AsyncOpenAI(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        )
        set_default_openai_client(client, use_for_tracing=False)
        set_default_openai_api("chat_completions")

        instructions = get_prompt("recall/recall_instructions.txt").format(
            search_rounds=search_rounds
        ).strip()

        agent = Agent(
            name="RecallAgent",
            instructions=instructions,
            model=llm_config.model_name,
            tools=[tool_recall],
        )

        agent_messages = cls._normalize_messages(messages)
        if not agent_messages:
            return {"injected_messages": [], "footprints": []}

        prompt_logger.info(json.dumps({
            "type": "memory_recall_prompt",
            "source": "RecallService.perform_recall",
            "friend_id": friend_id,
            "model": llm_config.model_name,
            "instructions": instructions,
            "messages": agent_messages,
            "search_rounds": search_rounds,
            "event_topk": event_topk,
            "similarity_threshold": threshold,
        }, ensure_ascii=False, default=str))

        result = await Runner.run(agent, agent_messages)

        tool_outputs: List[Dict[str, Any]] = []
        footprints: List[Dict[str, Any]] = []
        
        # 用于最后生成 mock 注入的消息
        all_merged_events = []
        last_tool_call_id = None
        last_tool_call_args = None

        for item in result.new_items:
            if isinstance(item, ToolCallItem):
                name, call_id, arguments = cls._extract_tool_call(item)
                last_tool_call_id = call_id or last_tool_call_id
                last_tool_call_args = arguments or last_tool_call_args
                footprints.append({
                    "type": "tool_call",
                    "name": name,
                    "arguments": arguments
                })
            elif isinstance(item, ToolCallOutputItem):
                output = item.output
                if isinstance(output, dict) and "events" in output:
                    tool_outputs.append(output)
                footprints.append({
                    "type": "tool_result",
                    "name": "recall_memory", # 目前只有一个工具
                    "result": output
                })
            elif isinstance(item, ReasoningItem):
                reasoning = cls._extract_reasoning_text(item)
                if reasoning:
                    footprints.append({
                        "type": "thinking",
                        "content": reasoning
                    })

        merged_events = cls._merge_events(tool_outputs, event_topk)

        if not last_tool_call_id:
            last_tool_call_id = f"recall_{uuid.uuid4().hex}"

        if not last_tool_call_args:
            last_user = next(
                (msg["content"] for msg in reversed(agent_messages) if msg.get("role") == "user"),
                "",
            )
            last_tool_call_args = json.dumps({"query": last_user or ""}, ensure_ascii=False)

        tool_call_item = {
            "type": "function_call",
            "call_id": last_tool_call_id,
            "name": "recall_memory",
            "arguments": last_tool_call_args,
        }
        tool_result_item = {
            "type": "function_call_output",
            "call_id": last_tool_call_id,
            "output": json.dumps({"events": merged_events}, ensure_ascii=False),
        }

        logger.info("RecallService merged %s events, generated %s footprints", len(merged_events), len(footprints))

        return {
            "injected_messages": [tool_call_item, tool_result_item],
            "footprints": footprints
        }
