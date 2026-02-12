from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.friend import Friend
from app.models.group import GroupMessage, GroupSession
from app.services.memo.constants import DEFAULT_USER_ID

from agents import RunConfig, Runner
from agents.items import ReasoningItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent
from openai.types.responses import ResponseTextDeltaEvent

from app.services.reasoning_stream import extract_reasoning_delta

# Story 09-06: 控制符常量
CTRL_NO_REPLY = "<CTRL:NO_REPLY>"


def _strip_message_tags(content: Optional[str]) -> Optional[str]:
    if not content:
        return content
    import re

    parts = re.findall(r"<message>(.*?)</message>", content, re.DOTALL)
    if parts:
        return " ".join(part.strip() for part in parts if part.strip())
    return re.sub(r"</?message>", "", content).strip()


def create_group_session(
    db: Session,
    group_id: int,
    title: Optional[str] = None,
    session_type: str = "normal",
) -> GroupSession:
    session = GroupSession(group_id=group_id, title=title or "群聊会话", session_type=session_type)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def end_active_sessions(db: Session, group_id: int, session_type: Optional[str] = None) -> List[GroupSession]:
    query = db.query(GroupSession).filter(GroupSession.group_id == group_id, GroupSession.ended == False)
    if session_type is not None:
        query = query.filter(GroupSession.session_type == session_type)
    sessions = query.all()
    if not sessions:
        return []
    now_time = datetime.now(timezone.utc)
    for session in sessions:
        session.ended = True
        session.update_time = now_time
    db.commit()
    return sessions


def create_user_message(
    db: Session,
    group_id: int,
    session_id: int,
    sender_id: str,
    content: str,
    message_type: str = "text",
    mentions: Optional[List[str]] = None,
) -> GroupMessage:
    db_message = GroupMessage(
        group_id=group_id,
        session_id=session_id,
        sender_id=sender_id,
        sender_type="user",
        content=content,
        message_type=message_type,
        mentions=mentions,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def create_ai_placeholder(
    db: Session,
    group_id: int,
    session_id: int,
    friend_id: int,
    message_type: str = "text",
    debate_side: Optional[str] = None,
) -> GroupMessage:
    db_ai_msg = GroupMessage(
        group_id=group_id,
        session_id=session_id,
        sender_id=str(friend_id),
        sender_type="friend",
        content="",
        message_type=message_type,
        debate_side=debate_side,
    )
    db.add(db_ai_msg)
    db.commit()
    db.refresh(db_ai_msg)
    return db_ai_msg


def touch_session(db: Session, session: GroupSession) -> None:
    now_time = datetime.now(timezone.utc)
    session.last_message_time = now_time
    session.update_time = now_time
    db.commit()


def touch_session_by_id(db: Session, session_id: int) -> Optional[GroupSession]:
    session = db.query(GroupSession).filter(GroupSession.id == session_id).first()
    if not session:
        return None
    touch_session(db, session)
    return session


def fetch_group_history(
    db: Session,
    group_id: int,
    session_id: Optional[int],
    before_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[GroupMessage]:
    query = db.query(GroupMessage).filter(GroupMessage.group_id == group_id)
    if session_id is not None:
        query = query.filter(GroupMessage.session_id == session_id)
    if before_id is not None:
        query = query.filter(GroupMessage.id < before_id)
    query = query.order_by(GroupMessage.create_time.desc())
    if limit is not None:
        query = query.limit(limit)
    history_msgs = query.all()
    history_msgs.reverse()
    return history_msgs


def build_name_map(
    db: Session,
    messages: List[GroupMessage],
    default_user_name: str = "我",
    default_user_id: str = DEFAULT_USER_ID,
) -> Dict[str, str]:
    member_ids = {msg.sender_id for msg in messages}
    friend_ids = []
    for mid in member_ids:
        try:
            friend_ids.append(int(mid))
        except (ValueError, TypeError):
            continue

    friends_data: List[Friend] = []
    if friend_ids:
        friends_data = db.query(Friend).filter(Friend.id.in_(friend_ids)).all()

    name_map = {str(f.id): f.name for f in friends_data}
    if default_user_id:
        name_map[str(default_user_id)] = default_user_name
    return name_map


def split_rounds(history_msgs: List[GroupMessage], self_id: int) -> List[dict]:
    rounds: List[dict] = []
    current_round = None
    for msg in history_msgs:
        if msg.sender_type == "user":
            if current_round:
                rounds.append(current_round)
            current_round = {"user": msg, "others": [], "self": None}
        else:
            if current_round:
                if msg.sender_type == "friend" and msg.sender_id == str(self_id):
                    current_round["self"] = msg
                else:
                    current_round["others"].append(msg)
            else:
                # 历史开头的非用户消息，先忽略或归入虚拟轮次
                pass
    if current_round:
        rounds.append(current_round)
    return rounds


def build_other_members_text(others: List[GroupMessage], name_map: Dict[str, str]) -> str:
    others_content = "\n".join([f"{name_map.get(m.sender_id, '未知')}: {m.content}" for m in others])
    return others_content or "(empty)"


def build_group_context(
    history_msgs: List[GroupMessage],
    name_map: Dict[str, str],
    self_id: int,
    current_user_msg: str,
    user_msg_id: int,
    current_other_members: str,
    mention_result: str,
    injected_recall_messages: Optional[List[dict]] = None,
    ctrl_no_reply: str = CTRL_NO_REPLY,
) -> List[dict]:
    agent_messages: List[dict] = []
    rounds = split_rounds(history_msgs, self_id)

    for r in rounds:
        u_msg = r["user"]
        agent_messages.append({"role": "user", "content": u_msg.content})

        others_content = build_other_members_text(r["others"], name_map)
        tc_id_hist = f"call_get_msgs_{u_msg.id}"
        agent_messages.append({
            "type": "function_call",
            "call_id": tc_id_hist,
            "name": "get_other_members_messages",
            "arguments": "{}",
        })
        agent_messages.append({
            "type": "function_call_output",
            "call_id": tc_id_hist,
            "output": others_content,
        })

        if r["self"] and r["self"].content.strip():
            agent_messages.append({"role": "assistant", "content": r["self"].content})
        else:
            agent_messages.append({"role": "assistant", "content": ctrl_no_reply})

    agent_messages.append({"role": "user", "content": current_user_msg})

    # Gemini through LiteLLM requires function_call turns to appear
    # immediately after a user turn (or a function response turn).
    if injected_recall_messages:
        agent_messages.extend(injected_recall_messages)

    tc_id_curr = f"call_curr_msgs_{user_msg_id}"
    agent_messages.append({
        "type": "function_call",
        "call_id": tc_id_curr,
        "name": "get_other_members_messages",
        "arguments": "{}",
    })
    agent_messages.append({
        "type": "function_call_output",
        "call_id": tc_id_curr,
        "output": current_other_members or "(empty)",
    })

    tc_id_ment = f"call_ment_{user_msg_id}"
    agent_messages.append({
        "type": "function_call",
        "call_id": tc_id_ment,
        "name": "is_mentioned",
        "arguments": "{}",
    })
    agent_messages.append({
        "type": "function_call_output",
        "call_id": tc_id_ment,
        "output": mention_result,
    })

    return agent_messages


def build_system_prompt(
    root_template: str,
    persona_prompt: str,
    script_prompt: str,
    profile_data: str,
    segment_prompt: str,
    current_time: str,
) -> str:
    try:
        final_instructions = root_template.replace("{{role-play-prompt}}", persona_prompt)
        final_instructions = final_instructions.replace(
            "{{script-expression}}",
            f"\n\n{script_prompt}" if script_prompt else "",
        )
        final_instructions = final_instructions.replace(
            "{{user-profile}}",
            f"\n\n【用户信息】\n{profile_data}" if profile_data else "",
        )
        final_instructions = final_instructions.replace(
            "{{segment-instruction}}",
            f"\n\n{segment_prompt}" if segment_prompt else "",
        )
        final_instructions = final_instructions.replace("{{current-time}}", current_time)
        return final_instructions
    except Exception:
        return f"{persona_prompt}\n\n{script_prompt}\n\n{current_time}"


def build_agent_tools(*tools) -> List:
    return [tool for tool in tools if tool is not None]


def _extract_reasoning_text(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return str(
            raw.get("reasoning_content")
            or raw.get("reasoning")
            or raw.get("text")
            or raw.get("content")
            or ""
        )
    return str(
        getattr(raw, "reasoning_content", None)
        or getattr(raw, "reasoning", None)
        or getattr(raw, "text", None)
        or getattr(raw, "content", None)
        or ""
    )


async def stream_llm_to_queue(
    agent,
    agent_messages: List[dict],
    queue,
    enable_thinking: bool,
    sender_id: int,
    message_id: int,
    session_id: int,
    db: Session,
    sanitize_message_tags: bool = False,
) -> str:
    content_buffer = ""
    has_reasoning_item = False
    reasoning_stream_seen = False
    tool_call_names: Dict[str, str] = {}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    result = Runner.run_streamed(agent, agent_messages, run_config=RunConfig(trace_include_sensitive_data=True))

    buffer = ""
    is_thinking_tag = False
    THINK_START = "<think>"
    THINK_END = "</think>"
    saved_content = ""

    async for event in result.stream_events():
        if isinstance(event, RunItemStreamEvent) and event.name == "reasoning_item_created":
            if enable_thinking and isinstance(event.item, ReasoningItem):
                if not reasoning_stream_seen:
                    raw = event.item.raw_item
                    text = _extract_reasoning_text(raw)
                    if text:
                        has_reasoning_item = True
                        await queue.put({
                            "event": "model_thinking",
                            "data": {
                                "sender_id": str(sender_id),
                                "delta": text,
                                "message_id": message_id,
                            },
                        })
            continue

        if isinstance(event, RunItemStreamEvent) and event.name == "tool_called":
            if isinstance(event.item, ToolCallItem):
                raw = event.item.raw_item
                if isinstance(raw, dict):
                    name = raw.get("name")
                    call_id = raw.get("call_id")
                    arguments = raw.get("arguments")
                else:
                    name = getattr(raw, "name", None)
                    call_id = getattr(raw, "call_id", None)
                    arguments = getattr(raw, "arguments", None)

                if call_id and name:
                    tool_call_names[call_id] = name

                await queue.put({
                    "event": "tool_call",
                    "data": {
                        "sender_id": str(sender_id),
                        "tool_name": name or "tool",
                        "arguments": arguments,
                        "call_id": call_id,
                        "message_id": message_id,
                    },
                })
            continue

        if isinstance(event, RunItemStreamEvent) and event.name == "tool_output":
            if isinstance(event.item, ToolCallOutputItem):
                raw = event.item.raw_item
                if isinstance(raw, dict):
                    call_id = raw.get("call_id")
                else:
                    call_id = getattr(raw, "call_id", None)

                if call_id:
                    name = tool_call_names.get(call_id, "tool")
                else:
                    name = "tool"

                await queue.put({
                    "event": "tool_result",
                    "data": {
                        "sender_id": str(sender_id),
                        "tool_name": name,
                        "result": event.item.output,
                        "call_id": call_id,
                        "message_id": message_id,
                    },
                })
            continue

        if event.type == "raw_response_event" and enable_thinking:
            reasoning_delta = extract_reasoning_delta(event.data)
            if reasoning_delta:
                reasoning_stream_seen = True
                has_reasoning_item = True
                await queue.put({
                    "event": "model_thinking",
                    "data": {
                        "sender_id": str(sender_id),
                        "delta": reasoning_delta,
                        "message_id": message_id,
                    },
                })
                continue

        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            delta = event.data.delta
            if delta:
                content_buffer += delta
                buffer += delta

                while buffer:
                    if not is_thinking_tag:
                        start_idx = buffer.find(THINK_START)
                        if start_idx != -1:
                            if start_idx > 0:
                                msg_delta = buffer[:start_idx]
                                saved_content += msg_delta
                                await queue.put({
                                    "event": "message",
                                    "data": {
                                        "sender_id": str(sender_id),
                                        "delta": msg_delta,
                                        "message_id": message_id,
                                    },
                                })
                            buffer = buffer[start_idx + len(THINK_START):]
                            is_thinking_tag = True
                        else:
                            if "<" not in buffer:
                                saved_content += buffer
                                await queue.put({
                                    "event": "message",
                                    "data": {
                                        "sender_id": str(sender_id),
                                        "delta": buffer,
                                        "message_id": message_id,
                                    },
                                })
                                buffer = ""
                            else:
                                break
                    else:
                        end_idx = buffer.find(THINK_END)
                        if end_idx != -1:
                            if end_idx > 0 and enable_thinking and not has_reasoning_item:
                                think_chunk = buffer[:end_idx]
                                await queue.put({
                                    "event": "model_thinking",
                                    "data": {
                                        "sender_id": str(sender_id),
                                        "delta": think_chunk,
                                        "message_id": message_id,
                                    },
                                })

                            buffer = buffer[end_idx + len(THINK_END):]
                            is_thinking_tag = False
                        else:
                            if "</" not in buffer:
                                if enable_thinking and not has_reasoning_item:
                                    await queue.put({
                                        "event": "model_thinking",
                                        "data": {
                                            "sender_id": str(sender_id),
                                            "delta": buffer,
                                            "message_id": message_id,
                                        },
                                    })
                                buffer = ""
                            else:
                                break

    if buffer:
        if is_thinking_tag:
            if enable_thinking and not has_reasoning_item:
                await queue.put({
                    "event": "model_thinking",
                    "data": {
                        "sender_id": str(sender_id),
                        "delta": buffer,
                        "message_id": message_id,
                    },
                })
        else:
            saved_content += buffer
            await queue.put({
                "event": "message",
                "data": {
                    "sender_id": str(sender_id),
                    "delta": buffer,
                    "message_id": message_id,
                },
            })

    final_content = saved_content if saved_content else content_buffer
    final_content = final_content.replace(THINK_START, "").replace(THINK_END, "")
    if sanitize_message_tags:
        final_content = _strip_message_tags(final_content) or final_content

    persist_final_content(db, message_id, final_content, session_id)
    usage["completion_tokens"] = len(content_buffer)

    await queue.put({
        "event": "done",
        "data": {
            "sender_id": str(sender_id),
            "message_id": message_id,
            "session_id": session_id,
            "content": final_content,
            "usage": usage,
        },
    })

    return final_content


def persist_final_content(db: Session, ai_msg_id: int, final_content: str, session_id: int) -> None:
    db_msg = db.query(GroupMessage).filter(GroupMessage.id == ai_msg_id).first()
    if db_msg:
        db_msg.content = final_content
        db.commit()

    touch_session_by_id(db, session_id)
