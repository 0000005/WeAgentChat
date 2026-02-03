import json
import logging
import re
from typing import Optional

from agents import Agent, Runner, RunConfig
from openai.types.responses import ResponseOutputText, ResponseTextDeltaEvent
from sqlalchemy.orm import Session
from agents.items import MessageOutputItem
from agents.stream_events import RunItemStreamEvent

from app.prompt import get_prompt
from app.schemas.persona_generator import PersonaGenerateRequest, PersonaGenerateResponse
from app.services.llm_client import set_agents_default_client
from app.services.llm_service import llm_service
from app.services import provider_rules

logger = logging.getLogger(__name__)

def _strip_json_code_fences(content: Optional[str]) -> Optional[str]:
    if not content:
        return content
    text = content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


class PersonaGeneratorService:
    @staticmethod
    async def _stream_agent_events(
        agent: Agent,
        user_input: str,
        run_config: RunConfig,
        full_parts: list[str],
    ):
        result = Runner.run_streamed(
            agent,
            user_input,
            run_config=run_config,
        )
        async for event in result.stream_events():
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                delta = event.data.delta
                if delta:
                    full_parts.append(delta)
                    yield {"event": "delta", "data": {"delta": delta}}
                continue

            if isinstance(event, RunItemStreamEvent) and event.name == "message_output_created":
                if isinstance(event.item, MessageOutputItem):
                    message_text = ""
                    for part in event.item.raw_item.content:
                        if isinstance(part, ResponseOutputText):
                            message_text += part.text or ""
                    if message_text:
                        full_parts.append(message_text)
                        yield {"event": "delta", "data": {"delta": message_text}}
                continue

    @staticmethod
    async def generate_persona_stream(
        db: Session,
        request: PersonaGenerateRequest
    ):
        llm_config = llm_service.get_active_config(db)
        if not llm_config:
            yield {
                "event": "error",
                "data": {
                    "code": "config_not_found",
                    "detail": "LLM configuration not found. Please configure LLM settings first."
                }
            }
            return

        set_agents_default_client(llm_config, use_for_tracing=True)

        instructions = get_prompt("persona/generate_instructions.txt").strip()
        model_name = llm_service.normalize_model_name(llm_config.model_name)
        output_type = PersonaGenerateResponse if provider_rules.supports_json_mode(
            llm_config,
            llm_config.model_name,
        ) else None
        agent = Agent(
            name="PersonaGenerator",
            instructions=instructions,
            model=model_name,
            output_type=output_type,
        )

        user_input = f"请为我生成一个角色。用户描述：{request.description}"
        if request.name:
            user_input += f"\n姓名：{request.name}"

        run_config = RunConfig(trace_include_sensitive_data=True)
        full_parts: list[str] = []
        try:
            async for event_data in PersonaGeneratorService._stream_agent_events(
                agent,
                user_input,
                run_config,
                full_parts,
            ):
                yield event_data
        except Exception as e:
            if provider_rules.is_json_mode_unsupported_error(e):
                logger.warning(f"JSON mode unsupported, fallback to normal call: {e}")
                full_parts = []
                agent = Agent(
                    name="PersonaGenerator",
                    instructions=instructions,
                    model=model_name,
                )
                try:
                    async for event_data in PersonaGeneratorService._stream_agent_events(
                        agent,
                        user_input,
                        run_config,
                        full_parts,
                    ):
                        yield event_data
                except Exception as e2:
                    logger.error(f"LLM stream failed: {e2}")
                    yield {
                        "event": "error",
                        "data": {"code": "llm_error", "detail": f"LLM call failed: {str(e2)}"}
                    }
                    return
            else:
                logger.error(f"LLM stream failed: {e}")
                yield {
                    "event": "error",
                    "data": {"code": "llm_error", "detail": f"LLM call failed: {str(e)}"}
                }
                return

        full_content = "".join(full_parts)

        if not full_content:
            yield {
                "event": "error",
                "data": {"code": "empty_response", "detail": "LLM returned empty response."}
            }
            return

        parsed = PersonaGeneratorService._parse_llm_json(full_content)
        if not parsed:
            logger.error(f"Failed to parse LLM JSON response. Raw output:\n{full_content}")
            yield {
                "event": "error",
                "data": {
                    "code": "parse_error",
                    "detail": "Failed to parse LLM response as JSON. Check server logs for raw output."
                }
            }
            return

        missing_fields = [key for key in ["name", "description", "system_prompt", "initial_message"] if not parsed.get(key)]
        if missing_fields:
            yield {
                "event": "error",
                "data": {
                    "code": "missing_fields",
                    "detail": f"LLM response missing required fields: {', '.join(missing_fields)}"
                }
            }
            return

        yield {
            "event": "result",
            "data": {
                "name": parsed["name"],
                "description": parsed["description"],
                "system_prompt": parsed["system_prompt"],
                "initial_message": parsed["initial_message"]
            }
        }

    @staticmethod
    def _parse_llm_json(content: str) -> Optional[dict]:
        """
        尝试从 LLM 输出中解析 JSON。
        支持以下格式：
        1. 纯 JSON
        2. Markdown 代码块包裹的 JSON (```json ... ```)
        3. 普通代码块包裹的 JSON (``` ... ```)
        """
        if not content:
            return None
        
        # 清理内容
        json_str = _strip_json_code_fences(content)
        if not json_str:
            return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 尝试提取首个完整 JSON 对象
        depth = 0
        start_idx = None
        for idx, ch in enumerate(json_str):
            if ch == '{':
                if depth == 0:
                    start_idx = idx
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        candidate = json_str[start_idx:idx + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            start_idx = None
                            continue

        logger.debug("JSON parse failed: no valid object extracted")
        return None


persona_generator_service = PersonaGeneratorService()
