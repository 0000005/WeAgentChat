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


logger = logging.getLogger(__name__)


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
    ) -> List[Dict[str, Any]]:
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

        @function_tool(
            name_override="recall_memory",
            description_override="召回与问题最相关的历史事件。",
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

        instructions = (
            "你是一名记忆专家。你的任务是根据用户的提问，调用 recall_memory 工具召回相关的过往事件（Events）。"
            "你可以根据第一轮搜到的信息进行追问或深入搜索，直到找到最相关的记忆。"
            f"你最多可以调用工具 {search_rounds} 次，找到相关记忆后立即结束。"
            "最后只需结束通话，无需直接回答用户提问。"
        )

        agent = Agent(
            name="RecallAgent",
            instructions=instructions,
            model=llm_config.model_name,
            tools=[tool_recall],
        )

        agent_messages = cls._normalize_messages(messages)
        if not agent_messages:
            return []

        result = await Runner.run(agent, agent_messages)

        tool_outputs: List[Dict[str, Any]] = []
        tool_call_id: Optional[str] = None
        tool_call_arguments: Optional[str] = None
        reasoning_traces: List[str] = []
        tool_calls: List[Dict[str, Optional[str]]] = []

        for item in result.new_items:
            if isinstance(item, ToolCallItem):
                name, call_id, arguments = cls._extract_tool_call(item)
                if name == "recall_memory":
                    tool_call_id = call_id or tool_call_id
                    tool_call_arguments = arguments or tool_call_arguments
                    tool_calls.append(
                        {"call_id": call_id, "arguments": arguments}
                    )
            elif isinstance(item, ToolCallOutputItem):
                output = item.output
                if isinstance(output, dict) and "events" in output:
                    tool_outputs.append(output)
            elif isinstance(item, ReasoningItem):
                reasoning = cls._extract_reasoning_text(item)
                if reasoning:
                    reasoning_traces.append(reasoning)

        merged_events = cls._merge_events(tool_outputs, event_topk)

        if tool_calls:
            for idx, call in enumerate(tool_calls, start=1):
                args = call.get("arguments") or ""
                logger.info(
                    "RecallService round %s/%s call_id=%s args=%s",
                    idx,
                    len(tool_calls),
                    call.get("call_id"),
                    args,
                )
                if idx <= len(tool_outputs):
                    logger.info(
                        "RecallService round %s result events=%s",
                        idx,
                        len(tool_outputs[idx - 1].get("events", []) or []),
                    )
        else:
            logger.info("RecallService ran with 0 tool calls")

        if not tool_call_id:
            tool_call_id = f"recall_{uuid.uuid4().hex}"

        if not tool_call_arguments:
            last_user = next(
                (msg["content"] for msg in reversed(agent_messages) if msg.get("role") == "user"),
                "",
            )
            tool_call_arguments = json.dumps({"query": last_user or ""}, ensure_ascii=False)

        tool_call_item = {
            "type": "function_call",
            "call_id": tool_call_id,
            "name": "recall_memory",
            "arguments": tool_call_arguments,
        }
        tool_result_item = {
            "type": "function_call_output",
            "call_id": tool_call_id,
            "output": json.dumps({"events": merged_events}, ensure_ascii=False),
        }

        if reasoning_traces:
            logger.debug("Recall reasoning traces collected: %s", len(reasoning_traces))
        logger.info("RecallService merged %s events", len(merged_events))
        if merged_events:
            preview = []
            for event in merged_events[: min(5, len(merged_events))]:
                content = event.get("content") if isinstance(event, dict) else ""
                preview.append(content)
            logger.info("RecallService merged event preview=%s", preview)

        return [tool_call_item, tool_result_item]
