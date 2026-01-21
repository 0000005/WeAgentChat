import json
import logging
import re
from typing import Optional

from agents import Agent, Runner, RunConfig, set_default_openai_api, set_default_openai_client
from fastapi import HTTPException
from openai import AsyncOpenAI
from openai.types.responses import ResponseOutputText, ResponseTextDeltaEvent
from sqlalchemy.orm import Session
from agents.items import MessageOutputItem
from agents.stream_events import RunItemStreamEvent

from app.prompt import get_prompt
from app.schemas.persona_generator import PersonaGenerateRequest, PersonaGenerateResponse
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class PersonaGeneratorService:
    @staticmethod
    async def generate_persona(
        db: Session,
        request: PersonaGenerateRequest
    ) -> PersonaGenerateResponse:
        # 1. 获取 LLM 配置
        llm_config = llm_service.get_active_config(db)
        if not llm_config:
            raise HTTPException(
                status_code=500,
                detail="LLM configuration not found. Please configure LLM settings first."
            )

        # 2. 设置 OpenAI 客户端
        client = AsyncOpenAI(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        )
        set_default_openai_client(client, use_for_tracing=True)
        set_default_openai_api("chat_completions")

        # 3. 初始化 GeneratorAgent
        instructions = get_prompt("persona/generate_instructions.txt").strip()
        model_name = llm_service.normalize_model_name(llm_config.model_name)

        agent = Agent(
            name="PersonaGenerator",
            instructions=instructions,
            model=model_name,
        )

        # 4. 准备输入
        user_input = f"请为我生成一个角色。用户描述：{request.description}"
        if request.name:
            user_input += f"\n姓名：{request.name}"

        # 5. 运行 Agent
        try:
            result = await Runner.run(
                agent,
                user_input,
                run_config=RunConfig(trace_include_sensitive_data=True),
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"LLM call failed: {str(e)}"
            )
        
        # 6. 解析结果
        content = result.final_output
        if not content:
            raise HTTPException(
                status_code=502,
                detail="LLM returned empty response."
            )
        
        # 尝试解析 JSON
        parsed = PersonaGeneratorService._parse_llm_json(content)
        if not parsed:
            # 解析失败，记录原始响应到日志
            logger.error(f"Failed to parse LLM JSON response. Raw output:\n{content}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to parse LLM response as JSON. Check server logs for raw output."
            )
        
        missing_fields = [key for key in ["name", "description", "system_prompt", "initial_message"] if not parsed.get(key)]
        if missing_fields:
            raise HTTPException(
                status_code=502,
                detail=f"LLM response missing required fields: {', '.join(missing_fields)}"
            )

        return PersonaGenerateResponse(
            name=parsed["name"],
            description=parsed["description"],
            system_prompt=parsed["system_prompt"],
            initial_message=parsed["initial_message"]
        )

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

        client = AsyncOpenAI(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        )
        set_default_openai_client(client, use_for_tracing=True)
        set_default_openai_api("chat_completions")

        instructions = get_prompt("persona/generate_instructions.txt").strip()
        model_name = llm_service.normalize_model_name(llm_config.model_name)
        agent = Agent(
            name="PersonaGenerator",
            instructions=instructions,
            model=model_name,
        )

        user_input = f"请为我生成一个角色。用户描述：{request.description}"
        if request.name:
            user_input += f"\n姓名：{request.name}"

        full_content = ""
        try:
            result = Runner.run_streamed(
                agent,
                user_input,
                run_config=RunConfig(trace_include_sensitive_data=True),
            )
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    delta = event.data.delta
                    if delta:
                        full_content += delta
                        yield {"event": "delta", "data": {"delta": delta}}
                    continue

                if isinstance(event, RunItemStreamEvent) and event.name == "message_output_created":
                    if isinstance(event.item, MessageOutputItem):
                        message_text = ""
                        for part in event.item.raw_item.content:
                            if isinstance(part, ResponseOutputText):
                                message_text += part.text or ""
                        if message_text:
                            full_content += message_text
                            yield {"event": "delta", "data": {"delta": message_text}}
                    continue
        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            yield {
                "event": "error",
                "data": {"code": "llm_error", "detail": f"LLM call failed: {str(e)}"}
            }
            return

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
        content = content.strip()
        
        # 移除代码块围栏，保留中间内容
        lines = []
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('```'):
                continue
            lines.append(line)

        json_str = '\n'.join(lines).strip()

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
