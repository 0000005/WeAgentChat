import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agents import Agent, Runner, function_tool, set_default_openai_api, set_default_openai_client
from agents.items import ReasoningItem, ToolCallItem, ToolCallOutputItem
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.models.llm import LLMConfig
from app.services.memo.bridge import MemoService
from app.services.llm_service import llm_service
from app.services.settings_service import SettingsService
from app.prompt import get_prompt


logger = logging.getLogger(__name__)
prompt_logger = logging.getLogger("prompt_trace")


class RecallService:
    """
    记忆召回服务类。
    负责协调 "回忆 Agent" (RecallAgent) 执行多轮搜索，从记忆库中提取与当前对话相关的事件。
    """

    @staticmethod
    def _normalize_messages(messages: Iterable[Any]) -> List[Dict[str, str]]:
        """
        标准化消息列表。
        将各种可能的消息对象（字典或带有 role/content 属性的对象）转化为标准的字典格式。
        """
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
        """
        从 ReasoningItem 中提取思维链（CoT）文本。
        """
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
        """
        从 ToolCallItem 中提取工具调用的详细信息：名称、调用ID、参数。
        """
        raw = item.raw_item
        if isinstance(raw, dict):
            return raw.get("name"), raw.get("call_id"), raw.get("arguments")
        name = getattr(raw, "name", None)
        call_id = getattr(raw, "call_id", None)
        arguments = getattr(raw, "arguments", None)
        return name, call_id, arguments

    @staticmethod
    def _merge_events(outputs: Iterable[Dict[str, Any]], max_events: int) -> List[Dict[str, Any]]:
        """
        合并多次召回产生的记忆事件。
        根据日期和内容进行去重，并保留相似度最高的记录。
        """
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
                # 如果同一事件出现多次，保留相似度更高的那个
                existing_similarity = existing.get("similarity") or 0
                new_similarity = event.get("similarity") or 0
                if new_similarity > existing_similarity:
                    merged[key] = event
        merged_events = list(merged.values())
        # 按相似度降序排列
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
        执行记忆召回逻辑。
        
        该方法启动一个 RecallAgent，模拟 Function Calling 过程去召回记忆。
        
        返回:
            {
                "injected_messages": [mock_tool_call, mock_tool_result], # 用于注入到主对话历史中的伪造消息
                "footprints": [ # 执行过程中的足迹，用于前端展示
                    {"type": "thinking", "content": "..."},
                    {"type": "tool_call", "name": "...", "arguments": "..."},
                    {"type": "tool_result", "name": "...", "result": "..."},
                ]
            }
        """
        # 1. 获取 LLM 配置和系统设置
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

        # 2. 定义 Agent 手里的“召回工具”
        tool_description = get_prompt("recall/recall_tool_description.txt").strip()

        @function_tool(
            name_override="recall_memory",
            description_override=tool_description,
        )
        async def tool_recall(query: str) -> Dict[str, Any]:
            # 工具逻辑：调用向量检索服务
            return await MemoService.recall_memory(
                user_id=user_id,
                space_id=space_id,
                query=query,
                friend_id=friend_id,
                topk_event=event_topk,
                threshold=threshold,
            )

        # 3. 设置 OpenAI 客户端
        client = AsyncOpenAI(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        )
        set_default_openai_client(client, use_for_tracing=False)
        set_default_openai_api("chat_completions")

        # 4. 初始化 RecallAgent
        # 内部逻辑使用 UTC，但给 RecallAgent 的指示词建议使用北京时间以便更好地进行相对时间检索
        beijing_tz = timezone(timedelta(hours=8))
        now_time = datetime.now(timezone.utc).astimezone(beijing_tz)
        weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        current_time = f"{now_time:%Y-%m-%d %H}点 {weekday_map[now_time.weekday()]}"
        instructions = get_prompt("recall/recall_instructions.txt").format(
            search_rounds=search_rounds,
            current_time=current_time,
        ).strip()

        model_name = llm_service.normalize_model_name(llm_config.model_name)
        agent = Agent(
            name="RecallAgent",
            instructions=instructions,
            model=model_name,
            tools=[tool_recall],
        )

        # 5. 准备对话上下文并运行 Agent
        agent_messages = cls._normalize_messages(messages)
        if not agent_messages:
            return {"injected_messages": [], "footprints": []}

        prompt_logger.info(json.dumps({
            "type": "memory_recall_prompt",
            "source": "RecallService.perform_recall",
            "friend_id": friend_id,
            "model": model_name,
            "instructions": instructions,
            "messages": agent_messages,
            "search_rounds": search_rounds,
            "event_topk": event_topk,
            "similarity_threshold": threshold,
        }, ensure_ascii=False, default=str))

        # 执行 Agent 逻辑
        result = await Runner.run(agent, agent_messages)

        # 6. 处理 Agent 运行结果，提取足迹和召回的事件
        tool_outputs: List[Dict[str, Any]] = []
        footprints: List[Dict[str, Any]] = []
        
        last_tool_call_id = None
        last_tool_call_args = None

        for item in result.new_items:
            if isinstance(item, ToolCallItem):
                # 记录工具支出
                name, call_id, arguments = cls._extract_tool_call(item)
                last_tool_call_id = call_id or last_tool_call_id
                last_tool_call_args = arguments or last_tool_call_args
                footprints.append({
                    "type": "tool_call",
                    "name": name,
                    "arguments": arguments
                })
            elif isinstance(item, ToolCallOutputItem):
                # 收集工具返回的事件数据
                output = item.output
                if isinstance(output, dict) and "events" in output:
                    tool_outputs.append(output)
                footprints.append({
                    "type": "tool_result",
                    "name": "recall_memory",
                    "result": output
                })
            elif isinstance(item, ReasoningItem):
                # 记录 Agent 的思考过程
                reasoning = cls._extract_reasoning_text(item)
                if reasoning:
                    footprints.append({
                        "type": "thinking",
                        "content": reasoning
                    })

        # 7. 对多次搜索的结果进行合并去重
        merged_events = cls._merge_events(tool_outputs, event_topk)

        # 8. 构造“伪造消息对”用于注入主对话历史
        # 即使 Agent 没调工具或出错，我们也确保有一个基本的注入结构
        if not last_tool_call_id:
            last_tool_call_id = f"recall_{uuid.uuid4().hex}"

        if not last_tool_call_args:
            # 兜底：使用用户最后一句消息作为 query
            last_user = next(
                (msg["content"] for msg in reversed(agent_messages) if msg.get("role") == "user"),
                "",
            )
            last_tool_call_args = json.dumps({"query": last_user or ""}, ensure_ascii=False)

        # 伪造模型的一次 Function Call 动作
        tool_call_item = {
            "type": "function_call",
            "call_id": last_tool_call_id,
            "name": "recall_memory",
            "arguments": last_tool_call_args,
        }
        # 伪造该 Function Call 的返回结果（即我们合规后的记忆事件）
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

