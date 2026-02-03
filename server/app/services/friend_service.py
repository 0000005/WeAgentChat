from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timezone
from app.models.friend import Friend
from app.models.chat import ChatSession, Message
from app.services.llm_service import llm_service
from app.schemas.friend import (
    FriendCreate,
    FriendUpdate,
)
from app.services import provider_rules
from app.services.llm_client import set_agents_default_client
from app.prompt.loader import load_prompt
from openai.types.responses import ResponseOutputText, ResponseTextDeltaEvent
from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
from agents.items import MessageOutputItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent
import json
import logging

def get_friend(db: Session, friend_id: int) -> Optional[Friend]:
    return db.query(Friend).filter(Friend.id == friend_id, Friend.deleted == False).first()

import re

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

def _strip_message_tags(content: Optional[str]) -> Optional[str]:
    if not content:
        return content
    # 提取所有 <message> 标签内容并用空格合并
    parts = re.findall(r'<message>(.*?)</message>', content, re.DOTALL)
    if parts:
        return " ".join(part.strip() for part in parts if part.strip())
    # 兜底：如果没有匹配到完整标签但包含标签字符，直接剔除所有标签文本
    return re.sub(r'</?message>', '', content).strip()

def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    return model_name.split("/", 1)[-1].lower()

def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")

def _repair_json_text(text: str) -> str:
    repaired = re.sub(r':\s*([《【])', r': "\1', text)
    repaired = re.sub(r'([^\\])""', r'\1"', repaired)
    repaired = re.sub(r'([。！？\.\!\?])""', r'\1"', repaired)

    def _quote_bare_value(match: re.Match) -> str:
        prefix = match.group("prefix")
        value = match.group("value").strip()
        value = value.replace('"', '\\"')
        return f'{prefix}"{value}"'

    repaired = re.sub(
        r'(?P<prefix>"(?:name|reason|description_hint)"\s*:\s*)(?P<value>[^"\{\[\d\-tfn][^,\n}]*)',
        _quote_bare_value,
        repaired,
        flags=re.IGNORECASE,
    )
    return repaired

def _extract_first_json_value(text: str) -> Optional[object]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r'[\{\[]', text):
        start = match.start()
        try:
            value, _ = decoder.raw_decode(text[start:])
            return value
        except json.JSONDecodeError:
            continue
    return None

async def _stream_agent_events(
    agent: Agent,
    user_input: str,
    run_config: RunConfig,
    full_parts: list[str],
    tool_payloads: list[object],
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

        if isinstance(event, RunItemStreamEvent) and event.name == "tool_called":
            if isinstance(event.item, ToolCallItem):
                raw = event.item.raw_item
                if isinstance(raw, dict):
                    name = raw.get("name")
                    arguments = raw.get("arguments")
                else:
                    name = getattr(raw, "name", None)
                    arguments = getattr(raw, "arguments", None)
                if name == "submit_recommendations" and arguments:
                    payload = None
                    if isinstance(arguments, dict):
                        payload = arguments
                    elif isinstance(arguments, str):
                        try:
                            payload = json.loads(arguments)
                        except json.JSONDecodeError:
                            payload = None
                    if payload is not None:
                        tool_payloads.append(payload)
            continue

        if isinstance(event, RunItemStreamEvent) and event.name == "tool_call_output":
            if isinstance(event.item, ToolCallOutputItem):
                output = event.item.output
                if isinstance(output, dict):
                    tool_payloads.append(output)
            continue

def get_friends(db: Session, skip: int = 0, limit: int = 100) -> List[Friend]:
    # 子查询：获取每个好友的最新消息ID（通过 ChatSession 连接）
    latest_message_subquery = (
        db.query(
            ChatSession.friend_id,
            func.max(Message.id).label("max_id")
        )
        .join(Message, ChatSession.id == Message.session_id)
        .filter(Message.deleted == False, ChatSession.deleted == False)
        .group_by(ChatSession.friend_id)
        .subquery()
    )

    # 主查询：连接好友和最新消息
    query = (
        db.query(Friend, Message.content, Message.role, Message.create_time)
        .outerjoin(latest_message_subquery, Friend.id == latest_message_subquery.c.friend_id)
        .outerjoin(Message, Message.id == latest_message_subquery.c.max_id)
        .filter(Friend.deleted == False)
        # 排序：置顶优先，其次按最后消息时间，最后按更新时间
        .order_by(
            Friend.pinned_at.desc().nulls_last(), 
            Message.create_time.desc().nulls_last(), 
            Friend.update_time.desc()
        )
        .offset(skip)
        .limit(limit)
    )

    results = []
    for friend, content, role, msg_time in query.all():
        # 将消息内容绑定到 friend 对象（临时属性，以便 Pydantic 转换）
        friend.last_message = _strip_message_tags(content)
        friend.last_message_role = role
        friend.last_message_time = msg_time
        results.append(friend)
    
    return results

def create_friend(db: Session, friend: FriendCreate) -> Friend:
    db_friend = Friend(
        name=friend.name,
        description=friend.description,
        system_prompt=friend.system_prompt,
        is_preset=friend.is_preset,
        avatar=friend.avatar,
        script_expression=friend.script_expression,
        temperature=friend.temperature,
        top_p=friend.top_p,
    )
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    return db_friend

def update_friend(db: Session, friend_id: int, friend_in: FriendUpdate) -> Optional[Friend]:
    db_friend = get_friend(db, friend_id)
    if not db_friend:
        return None
    
    update_data = friend_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_friend, field, value)
    
    db.add(db_friend)
    db.commit()
    db.refresh(db_friend)
    return db_friend

def delete_friend(db: Session, friend_id: int) -> bool:
    db_friend = get_friend(db, friend_id)
    if not db_friend:
        return False
    
    # 逻辑删除
    db_friend.deleted = True
    db.add(db_friend)
    db.commit()
    return True

def ensure_initial_message(db: Session, friend_id: int, initial_message: Optional[str] = None) -> Optional[Message]:
    """
    确保好友有初始招呼消息。如果没有 session，则创建一个并添加初始消息。
    """
    # 检查是否已有 session
    existing_session = db.query(ChatSession).filter(ChatSession.friend_id == friend_id, ChatSession.deleted == False).first()
    if existing_session:
        return None

    if not initial_message:
        initial_message = "你好！很高兴见到你。"

    # 创建 session
    db_session = ChatSession(
        friend_id=friend_id,
        title="新对话",
        last_message_time=datetime.now(timezone.utc)
    )
    db.add(db_session)
    db.flush() # 获取 ID

    # 创建消息
    db_message = Message(
        session_id=db_session.id,
        friend_id=friend_id,
        role="assistant",
        content=initial_message
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message



async def recommend_friends_by_topic_stream(db: Session, topic: str, exclude_names: List[str] = []):
    """
    根据话题推荐适合的 AI 好友（流式返回）。
    
    Yields:
        dict: SSE 事件，格式为 {"event": "delta"|"result"|"error", "data": {...}}
    """
    from jinja2 import Template
    
    logger = logging.getLogger(__name__)
    
    # 1. 输入验证
    topic = topic.strip()
    if not topic:
        yield {"event": "error", "data": {"detail": "话题不能为空"}}
        return
    if len(topic) < 2:
        yield {"event": "error", "data": {"detail": "话题至少需要2个字符"}}
        return
    if len(topic) > 200:
        yield {"event": "error", "data": {"detail": "话题长度不能超过200字符"}}
        return
    
    logger.info(f"[FriendRecommendationStream] Starting for topic: {topic[:50]}, exclude: {exclude_names}")
    
    # 2. Load & Render Prompt
    try:
        content = load_prompt("persona/friend_recommendation.txt")
        template = Template(content)
        system_prompt = template.render(topic=topic, exclude_names=exclude_names)
    except Exception as e:
        logger.error(f"[FriendRecommendationStream] Prompt failed: {e}")
        yield {"event": "error", "data": {"detail": "推荐功能配置加载失败"}}
        return

    # 3. 获取 LLM 配置
    llm_config = llm_service.get_active_config(db)
    if not llm_config:
        yield {"event": "error", "data": {"detail": "请先在设置中配置 LLM 模型"}}
        return
    
    # 4. Call LLM in Stream Mode (Agents)
    set_agents_default_client(llm_config, timeout=60.0, use_for_tracing=True)

    raw_model_name = llm_config.model_name
    model_name = llm_service.normalize_model_name(raw_model_name)
    use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)

    if use_litellm:
        from agents.extensions.models.litellm_model import LitellmModel

        gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
        gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
        agent_model = LitellmModel(
            model=gemini_model_name,
            base_url=gemini_base_url,
            api_key=llm_config.api_key,
        )
    else:
        agent_model = model_name

    model_settings = ModelSettings(temperature=0.7) if _supports_sampling(model_name) else ModelSettings()
    tool_description = "提交好友推荐结果，参数必须为 JSON 对象：{recommendations: [{name, reason, description_hint}]}"

    @function_tool(
        name_override="submit_recommendations",
        description_override=tool_description,
        strict_mode=False,
    )
    async def submit_recommendations(recommendations: List[dict]) -> dict:
        return {"recommendations": recommendations}

    agent = Agent(
        name="FriendRecommendation",
        instructions=system_prompt,
        model=agent_model,
        model_settings=model_settings,
        tools=[submit_recommendations],
    )

    run_config = RunConfig(trace_include_sensitive_data=True)
    full_parts: list[str] = []
    tool_payloads: list[object] = []
    try:
        async for event_data in _stream_agent_events(
            agent,
            "请生成推荐结果并调用 submit_recommendations 工具提交。",
            run_config,
            full_parts,
            tool_payloads,
        ):
            yield event_data
    except Exception as e:
        logger.error(f"[FriendRecommendationStream] LLM call failed: {e}")
        yield {"event": "error", "data": {"detail": f"AI 调用失败: {str(e)}"}}
        return

    full_content = "".join(full_parts)
    
    # 5. Parse Final Result
    if not full_content and not tool_payloads:
        yield {"event": "error", "data": {"detail": "AI 返回了空结果"}}
        return
    
    logger.info(f"[FriendRecommendationStream] Full LLM response:\n{full_content}")
    
    # Cleanup markdown
    result_text = _strip_json_code_fences(full_content) or ""
    logger.debug(f"[FriendRecommendationStream] Raw result_text:\n{result_text}")

    data = None
    if tool_payloads:
        data = tool_payloads[-1]
    else:
        logger.warning("[FriendRecommendationStream] Tool call missing; fallback to parse text output.")
        try:
            data = json.loads(result_text)
        except json.JSONDecodeError:
            repaired_text = _repair_json_text(result_text)
            logger.debug(f"[FriendRecommendationStream] Repaired result_text:\n{repaired_text}")
            try:
                data = json.loads(repaired_text)
            except json.JSONDecodeError:
                data = _extract_first_json_value(repaired_text)
                if data is None:
                    logger.error("[FriendRecommendationStream] JSON parse failed: unable to extract valid JSON object/array.")
                    logger.error(f"[FriendRecommendationStream] Failed to parse text:\n{repaired_text}")
                    yield {"event": "error", "data": {"detail": "AI 返回的格式无法解析"}}
                    return
    
    # Extract recommendations (期望为对象结构)
    raw_list = []
    if isinstance(data, dict):
        raw_list = data.get("recommendations", [])
        if not isinstance(raw_list, list):
            raw_list = []
        if not raw_list:
            raw_list = next((v for v in data.values() if isinstance(v, list)), [])
            if raw_list:
                logger.warning("[FriendRecommendationStream] LLM returned object without recommendations key; fallback to first list value.")
    elif isinstance(data, list):
        logger.warning("[FriendRecommendationStream] LLM returned array; wrapping into object.")
        raw_list = data
    
    items = []
    for item in raw_list:
        if isinstance(item, dict) and "name" in item and "reason" in item:
            desc = item.get("description_hint") or item.get("description") or item.get("reason")
            items.append({
                "name": item["name"],
                "reason": item["reason"],
                "description_hint": desc
            })
    
    if not items:
        yield {"event": "error", "data": {"detail": "AI 未能生成推荐结果"}}
        return
    
    yield {"event": "result", "data": {"recommendations": items}}

