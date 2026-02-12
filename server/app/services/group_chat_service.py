import json
import logging
import asyncio
import re
from typing import Any, List, Optional, AsyncGenerator, Dict, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.models.group import Group, GroupMember, GroupMessage, GroupSession
from app.models.friend import Friend
from app.schemas import group as group_schemas
from app.services.llm_service import llm_service
from app.services.settings_service import SettingsService
from app.services.embedding_service import embedding_service
from app.services import provider_rules
from app.services import group_chat_shared
from app.services.voice_message_service import generate_voice_payload_for_message
from app.prompt import get_prompt
from app.db.session import SessionLocal
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.services.memo.bridge import MemoService
from app.services.llm_client import set_agents_default_client


from openai.types.shared import Reasoning
from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
from agents.items import ToolCallItem, ToolCallOutputItem

logger = logging.getLogger(__name__)

GROUP_SMART_CONTEXT_RELEVANCE_THRESHOLD = 6.0
_group_message_locks: Dict[int, asyncio.Lock] = {}
_group_message_locks_guard = asyncio.Lock()

def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    return model_name.split("/", 1)[-1].lower()

def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")


def _parse_context_judgment_payload(payload: Any) -> Optional[Dict[str, int]]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return None
    if not isinstance(payload, dict):
        return None

    required_fields = ("topic_relevance", "intent_continuity", "entity_reference")
    normalized: Dict[str, int] = {}
    for field in required_fields:
        value = payload.get(field)
        if isinstance(value, bool):
            return None
        if not isinstance(value, int):
            return None
        if value < 0 or value > 10:
            return None
        normalized[field] = value
    return normalized


def _extract_tool_call(item: ToolCallItem) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    raw = item.raw_item
    if isinstance(raw, dict):
        return raw.get("name"), raw.get("call_id"), raw.get("arguments")
    name = getattr(raw, "name", None)
    call_id = getattr(raw, "call_id", None)
    arguments = getattr(raw, "arguments", None)
    return name, call_id, arguments


def _resolve_smart_context_llm_config(db: Session):
    configured = SettingsService.get_setting(db, "session", "smart_context_model", None)
    configured_id: Optional[int] = None

    if isinstance(configured, int):
        configured_id = configured
    elif isinstance(configured, str):
        stripped = configured.strip()
        if stripped:
            try:
                configured_id = int(stripped)
            except ValueError:
                logger.warning(
                    "[GroupSmartContext] Invalid smart_context_model setting value: %s",
                    configured,
                )

    if configured_id is not None:
        config = llm_service.get_config_by_id(db, configured_id)
        if config:
            logger.info(
                "[GroupSmartContext] Using dedicated judge model config_id=%s model=%s",
                configured_id,
                config.model_name,
            )
            return config
        logger.warning(
            "[GroupSmartContext] Config %s not found, fallback to active chat model.",
            configured_id,
        )

    active_config = llm_service.get_active_config(db)
    if active_config:
        logger.info(
            "[GroupSmartContext] Using active chat model config_id=%s model=%s",
            active_config.id,
            active_config.model_name,
        )
    return active_config


def _get_session_expiry_timeout_seconds(db: Session) -> int:
    raw_timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError):
        logger.warning(
            "[GroupSmartContext] Invalid passive_timeout value=%r, fallback to 1800s.",
            raw_timeout,
        )
        return 1800
    if timeout <= 0:
        logger.warning(
            "[GroupSmartContext] Non-positive passive_timeout value=%s, fallback to 1800s.",
            timeout,
        )
        return 1800
    return timeout


def _get_group_session_elapsed_seconds(
    session: GroupSession,
    now_time: datetime,
) -> Optional[float]:
    if not session.last_message_time:
        return None
    return max((now_time - session.last_message_time).total_seconds(), 0.0)


def _get_latest_group_session_any_state(db: Session, group_id: int) -> Optional[GroupSession]:
    return (
        db.query(GroupSession)
        .filter(
            GroupSession.group_id == group_id,
        )
        .order_by(GroupSession.id.desc())
        .first()
    )


def _get_latest_archived_group_session(db: Session, group_id: int) -> Optional[GroupSession]:
    return (
        db.query(GroupSession)
        .filter(
            GroupSession.group_id == group_id,
            GroupSession.session_type == "normal",
            GroupSession.ended == True,
        )
        .order_by(GroupSession.id.desc())
        .first()
    )


def _group_session_message_count(db: Session, session_id: int) -> int:
    return db.query(GroupMessage).filter(GroupMessage.session_id == session_id).count()


def _create_new_group_session(db: Session, group_id: int) -> GroupSession:
    return group_chat_shared.create_group_session(
        db,
        group_id=group_id,
        title=None,
        session_type="normal",
    )


def _end_group_session(db: Session, session: GroupSession, now_time: datetime) -> None:
    session.ended = True
    session.update_time = now_time
    db.commit()
    db.refresh(session)


def _unarchive_group_session(db: Session, session: GroupSession, now_time: datetime) -> None:
    session.ended = False
    session.update_time = now_time
    db.commit()
    db.refresh(session)


async def _get_group_message_lock(group_id: int) -> asyncio.Lock:
    lock = _group_message_locks.get(group_id)
    if lock:
        return lock

    async with _group_message_locks_guard:
        lock = _group_message_locks.get(group_id)
        if lock is None:
            lock = asyncio.Lock()
            _group_message_locks[group_id] = lock
        return lock


async def _judge_group_smart_context_relevance(
    db: Session,
    session: GroupSession,
    current_message: str,
) -> bool:
    logger.info(
        "[GroupSmartContext] Start judgment for session=%s group=%s",
        session.id,
        session.group_id,
    )
    llm_config = _resolve_smart_context_llm_config(db)
    if not llm_config:
        logger.warning("[GroupSmartContext] Missing LLM config, fallback to new session.")
        return False

    if not llm_config.capability_function_call:
        logger.warning(
            "[GroupSmartContext] Model %s does not support function call, fallback to new session.",
            llm_config.model_name,
        )
        return False

    history = (
        db.query(GroupMessage)
        .filter(GroupMessage.session_id == session.id)
        .order_by(GroupMessage.id.desc())
        .limit(8)
        .all()
    )
    history.reverse()

    friend_ids: List[int] = []
    for msg in history:
        if msg.sender_type != "friend":
            continue
        try:
            fid = int(msg.sender_id)
        except (TypeError, ValueError):
            continue
        if fid not in friend_ids:
            friend_ids.append(fid)
    friend_name_map: Dict[int, str] = {}
    if friend_ids:
        friends = db.query(Friend).filter(Friend.id.in_(friend_ids)).all()
        friend_name_map = {f.id: f.name for f in friends}

    logger.info(
        "[GroupSmartContext] Judgment context loaded for session=%s, history_count=%s",
        session.id,
        len(history),
    )

    history_lines: List[str] = []
    for msg in history:
        content = (msg.content or "").strip()
        if not content:
            continue
        if msg.sender_type == "user":
            role_name = "用户"
        elif msg.sender_type == "friend":
            try:
                fid = int(msg.sender_id)
            except (TypeError, ValueError):
                fid = None
            friend_name = friend_name_map.get(fid, "群友")
            role_name = f"群友({friend_name})"
        else:
            role_name = "系统"
        history_lines.append(f"{role_name}: {content}")

    history_text = "\n".join(history_lines) if history_lines else "(无历史消息)"
    prompt = get_prompt("chat/smart_context_judgment.txt").strip()
    user_input = (
        f"【最近对话历史】\n{history_text}\n\n"
        f"【用户新消息】\n{(current_message or '').strip()}"
    )

    @function_tool(
        name_override="context_judgment",
        description_override="评估用户新消息与会话历史的关联程度，按维度打分。",
    )
    async def context_judgment(
        topic_relevance: int,
        intent_continuity: int,
        entity_reference: int,
    ) -> Dict[str, int]:
        return {
            "topic_relevance": topic_relevance,
            "intent_continuity": intent_continuity,
            "entity_reference": entity_reference,
        }

    set_agents_default_client(llm_config, use_for_tracing=True)
    raw_model_name = llm_config.model_name
    if not raw_model_name:
        logger.warning("[GroupSmartContext] Empty model_name, fallback to new session.")
        return False

    model_name = llm_service.normalize_model_name(raw_model_name)
    use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)

    model_settings_kwargs: Dict[str, Any] = {}
    if _supports_sampling(model_name):
        temperature = 0.2
        if use_litellm and provider_rules.is_gemini_model(llm_config, raw_model_name):
            temperature = 1.0
        model_settings_kwargs["temperature"] = temperature
        model_settings_kwargs["top_p"] = 0.8
    if (
        llm_config.capability_reasoning
        and not use_litellm
        and provider_rules.supports_reasoning_effort(llm_config)
    ):
        model_settings_kwargs["reasoning"] = Reasoning(
            effort=provider_rules.get_reasoning_effort(llm_config, raw_model_name, False)
        )
    model_settings = ModelSettings(**model_settings_kwargs)

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

    agent = Agent(
        name="GroupSmartContextJudge",
        instructions=prompt,
        model=agent_model,
        model_settings=model_settings,
        tools=[context_judgment],
    )

    try:
        logger.info(
            "[GroupSmartContext] Invoking judge model=%s for session=%s",
            llm_config.model_name,
            session.id,
        )
        result = await asyncio.wait_for(
            Runner.run(
                agent,
                [{"role": "user", "content": user_input}],
                run_config=RunConfig(trace_include_sensitive_data=True),
            ),
            timeout=20.0,
        )
        logger.info("[GroupSmartContext] Judge completed for session=%s", session.id)
    except Exception as e:
        logger.warning(
            "[GroupSmartContext] LLM judgment failed, fallback to new session. session=%s model=%s error_type=%s error=%r",
            session.id,
            llm_config.model_name,
            type(e).__name__,
            e,
            exc_info=True,
        )
        return False

    scores: Optional[Dict[str, int]] = None
    for item in result.new_items:
        if isinstance(item, ToolCallOutputItem):
            parsed = _parse_context_judgment_payload(item.output)
            if parsed:
                scores = parsed
        elif isinstance(item, ToolCallItem):
            name, _, arguments = _extract_tool_call(item)
            if name != "context_judgment":
                continue
            parsed = _parse_context_judgment_payload(arguments)
            if parsed:
                scores = parsed

    if not scores:
        item_types = [type(item).__name__ for item in (result.new_items or [])]
        logger.warning(
            "[GroupSmartContext] context_judgment tool call missing/invalid, fallback to new session. session=%s items=%s",
            session.id,
            item_types,
        )
        return False

    weighted_score = (
        scores["topic_relevance"] * 0.4
        + scores["intent_continuity"] * 0.4
        + scores["entity_reference"] * 0.2
    )
    is_related = weighted_score >= GROUP_SMART_CONTEXT_RELEVANCE_THRESHOLD

    logger.info(
        "[GroupSmartContext] Session %s score=%.2f (topic=%s, intent=%s, entity=%s) => related=%s",
        session.id,
        weighted_score,
        scores["topic_relevance"],
        scores["intent_continuity"],
        scores["entity_reference"],
        is_related,
    )
    return is_related


async def resolve_session_for_incoming_group_message(
    db: Session,
    group_id: int,
    current_message: str,
) -> GroupSession:
    timeout = _get_session_expiry_timeout_seconds(db)
    smart_context_enabled = SettingsService.get_setting(
        db, "session", "smart_context_enabled", False
    )
    now_time = datetime.now(timezone.utc)

    session = _get_latest_group_session_any_state(db, group_id)
    if not session:
        logger.info("[GroupSmartContext] No existing session for group=%s, creating new.", group_id)
        new_session = _create_new_group_session(db, group_id)
        logger.info(
            "[GroupSmartContext] Created new session=%s for group=%s",
            new_session.id,
            group_id,
        )
        return new_session

    logger.info(
        "[GroupSmartContext] Latest session picked group=%s session=%s ended=%s",
        group_id,
        session.id,
        session.ended,
    )

    if session.ended:
        elapsed = _get_group_session_elapsed_seconds(session, now_time)
        if elapsed is not None:
            logger.info(
                "[GroupSmartContext] Archived session %s elapsed=%.1fs timeout=%ss",
                session.id,
                elapsed,
                timeout,
            )
            if elapsed < timeout:
                _unarchive_group_session(db, session, now_time)
                logger.info(
                    "[GroupSmartContext] Archived session %s still within timeout, resurrect directly.",
                    session.id,
                )
                return session

        if not smart_context_enabled:
            logger.info(
                "[GroupSmartContext] Latest session=%s is archived and smart context disabled, create new.",
                session.id,
            )
            new_session = _create_new_group_session(db, group_id)
            logger.info(
                "[GroupSmartContext] Archived+disabled decision: old=%s new_session=%s",
                session.id,
                new_session.id,
            )
            return new_session

        logger.info(
            "[GroupSmartContext] Latest session=%s archived, start relevance judgment for possible unarchive.",
            session.id,
        )
        is_related = await _judge_group_smart_context_relevance(db, session, current_message)
        if is_related:
            _unarchive_group_session(db, session, now_time)
            logger.info(
                "[GroupSmartContext] Archived resurrection decision: reuse session=%s",
                session.id,
            )
            return session

        new_session = _create_new_group_session(db, group_id)
        logger.info(
            "[GroupSmartContext] Archived new-topic decision: old=%s new_session=%s",
            session.id,
            new_session.id,
        )
        return new_session

    if not session.last_message_time:
        if _group_session_message_count(db, session.id) == 0:
            archived_candidate = _get_latest_archived_group_session(db, group_id)
            if archived_candidate:
                archived_elapsed = _get_group_session_elapsed_seconds(archived_candidate, now_time)
                logger.info(
                    "[GroupSmartContext] Current session=%s is empty, checking archived session=%s for resurrection (elapsed=%s, timeout=%ss).",
                    session.id,
                    archived_candidate.id,
                    f"{archived_elapsed:.1f}s" if archived_elapsed is not None else "None",
                    timeout,
                )
                if smart_context_enabled:
                    logger.info(
                        "[GroupSmartContext] Empty-active override uses judgment (no direct resurrection). current=%s archived=%s",
                        session.id,
                        archived_candidate.id,
                    )
                    is_related = await _judge_group_smart_context_relevance(
                        db, archived_candidate, current_message
                    )
                    if is_related:
                        _end_group_session(db, session, now_time)
                        _unarchive_group_session(db, archived_candidate, now_time)
                        logger.info(
                            "[GroupSmartContext] Empty-active override: resurrect archived session=%s",
                            archived_candidate.id,
                        )
                        return archived_candidate
                else:
                    logger.info(
                        "[GroupSmartContext] Empty-active override skipped because smart context disabled. Keep current session=%s",
                        session.id,
                    )
        logger.info(
            "[GroupSmartContext] Session %s has no last_message_time, continue using it (skip judgment).",
            session.id,
        )
        return session

    elapsed = _get_group_session_elapsed_seconds(session, now_time) or 0.0
    logger.info(
        "[GroupSmartContext] Session %s elapsed=%.1fs timeout=%ss smart_enabled=%s",
        session.id,
        elapsed,
        timeout,
        bool(smart_context_enabled),
    )

    if elapsed < timeout:
        logger.info(
            "[GroupSmartContext] Session %s still active (elapsed=%.1fs < timeout=%ss), skip judgment.",
            session.id,
            elapsed,
            timeout,
        )
        return session

    if not smart_context_enabled:
        logger.info(
            "[GroupSmartContext] Smart context disabled, end old session=%s and create new.",
            session.id,
        )
        _end_group_session(db, session, now_time)
        new_session = _create_new_group_session(db, group_id)
        logger.info(
            "[GroupSmartContext] Disabled decision: ended=%s new_session=%s",
            session.id,
            new_session.id,
        )
        return new_session

    logger.info(
        "[GroupSmartContext] Smart context enabled, start relevance judgment for session=%s",
        session.id,
    )
    is_related = await _judge_group_smart_context_relevance(db, session, current_message)
    if is_related:
        session.update_time = now_time
        db.commit()
        db.refresh(session)
        logger.info("[GroupSmartContext] Resurrection decision: reuse session=%s", session.id)
        return session

    _end_group_session(db, session, now_time)
    new_session = _create_new_group_session(db, group_id)
    logger.info(
        "[GroupSmartContext] New-topic decision: ended=%s new_session=%s",
        session.id,
        new_session.id,
    )
    return new_session

class GroupChatService:
    @staticmethod
    def _get_group_friend_map(db: Session, group_id: int) -> Dict[int, Friend]:
        members = (
            db.query(GroupMember)
            .filter(GroupMember.group_id == group_id, GroupMember.member_type == "friend")
            .all()
        )
        friend_ids: List[int] = []
        for m in members:
            try:
                friend_ids.append(int(m.member_id))
            except (ValueError, TypeError):
                continue

        if not friend_ids:
            return {}

        friends = (
            db.query(Friend)
            .filter(Friend.id.in_(friend_ids), Friend.deleted == False)
            .all()
        )
        return {f.id: f for f in friends}

    @staticmethod
    def _load_manager_few_shots() -> List[dict]:
        messages: List[dict] = []
        for i in range(1, 6):
            try:
                user_text = get_prompt(f"chat/few_shot/group_manager_user_{i}.txt").strip()
                assistant_text = get_prompt(f"chat/few_shot/group_manager_assistant_{i}.txt").strip()
            except Exception as e:
                logger.warning(f"[GroupManager] Failed to load few-shot {i}: {e}")
                continue

            if user_text:
                messages.append({"role": "user", "content": user_text})
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text})
        return messages

    @staticmethod
    def _extract_json_payload(raw: str) -> Optional[object]:
        if not raw:
            return None
        raw = raw.strip()

        try:
            return json.loads(raw)
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            block = match.group(1).strip()
            try:
                return json.loads(block)
            except Exception:
                pass

        def _slice_between(text: str, start: str, end: str) -> Optional[str]:
            s = text.find(start)
            e = text.rfind(end)
            if s == -1 or e == -1 or e <= s:
                return None
            return text[s : e + 1]

        array_block = _slice_between(raw, "[", "]")
        if array_block:
            try:
                return json.loads(array_block)
            except Exception:
                pass

        obj_block = _slice_between(raw, "{", "}")
        if obj_block:
            try:
                return json.loads(obj_block)
            except Exception:
                pass

        return None

    @staticmethod
    def _parse_manager_ids(raw: str) -> List[int]:
        payload = GroupChatService._extract_json_payload(raw)
        if payload is None:
            return []

        candidates = []
        if isinstance(payload, list):
            candidates = payload
        elif isinstance(payload, dict):
            for key in ("speakerId", "speakerIds", "speaker_id", "speaker_ids", "speakers", "ids"):
                if key in payload:
                    candidates = payload.get(key) or []
                    break

        ids: List[int] = []
        seen = set()
        for item in candidates:
            val: Optional[int] = None
            if isinstance(item, int):
                val = item
            elif isinstance(item, float):
                if item.is_integer():
                    val = int(item)
            elif isinstance(item, str):
                if item.strip().isdigit():
                    val = int(item.strip())
            if val is None or val in seen:
                continue
            seen.add(val)
            ids.append(val)
        return ids

    @staticmethod
    def _fallback_speaker_ids(history_msgs: List[GroupMessage], friend_map: Dict[int, Friend]) -> List[int]:
        for msg in reversed(history_msgs):
            if msg.sender_type != "friend":
                continue
            try:
                fid = int(msg.sender_id)
            except (ValueError, TypeError):
                continue
            if fid in friend_map:
                return [fid]
        if friend_map:
            return [sorted(friend_map.keys())[0]]
        return []

    @staticmethod
    def _get_active_group_session(db: Session, group_id: int) -> Optional[GroupSession]:
        return (
            db.query(GroupSession)
            .filter(
                GroupSession.group_id == group_id,
                GroupSession.session_type == "normal",
                GroupSession.ended == False,
            )
            .order_by(GroupSession.update_time.desc(), GroupSession.id.desc())
            .first()
        )

    @staticmethod
    def _create_group_session(db: Session, group_id: int, title: Optional[str] = None) -> GroupSession:
        return group_chat_shared.create_group_session(db, group_id, title, session_type="normal")

    @staticmethod
    def get_or_create_session_for_group(db: Session, group_id: int) -> GroupSession:
        timeout = SettingsService.get_setting(db, "session", "passive_timeout", 1800)
        session = GroupChatService._get_active_group_session(db, group_id)

        if session:
            if session.last_message_time:
                now_time = datetime.now(timezone.utc)
                elapsed = (now_time - session.last_message_time).total_seconds()
                logger.info(f"[GroupSession] Session {session.id} (Group {group_id}): Last msg {session.last_message_time}, Elapsed {elapsed:.1f}s, Timeout {timeout}s")
                if elapsed > timeout:
                    logger.info(f"[GroupSession] Session {session.id} EXPIRED. Marking ended and creating new session. (NO memory extraction - group chat policy)")
                    session.ended = True
                    session.update_time = now_time
                    db.commit()
                    session = None
                else:
                    logger.info(f"[GroupSession] Session {session.id} ACTIVE. Continuing.")
            else:
                logger.info(f"[GroupSession] Session {session.id} has no last_message_time. Treated as ACTIVE/NEW.")
                return session

        if not session:
            logger.info(f"[GroupSession] Creating NEW session for group {group_id}...")
            session = GroupChatService._create_group_session(db, group_id)
            logger.info(f"[GroupSession] New session {session.id} created.")

        return session

    @staticmethod
    def create_group_session(db: Session, group_id: int) -> GroupSession:
        active_sessions = group_chat_shared.end_active_sessions(db, group_id, session_type="normal")
        if active_sessions:
            for session in active_sessions:
                logger.info(f"[GroupSession] Manual new session: Ending session {session.id}. (NO memory extraction - group chat policy)")
        return GroupChatService._create_group_session(db, group_id)

    @staticmethod
    async def _select_speakers_by_manager(
        db: Session,
        group_id: int,
        session_id: Optional[int],
        llm_config,
        friend_map: Optional[Dict[int, Friend]] = None
    ) -> List[Friend]:
        friend_map = friend_map or GroupChatService._get_group_friend_map(db, group_id)
        if not friend_map:
            logger.info(f"[GroupManager] No available friends in group {group_id}")
            return []

        member_lines: List[str] = []
        for fid in sorted(friend_map.keys()):
            friend = friend_map[fid]
            desc = (friend.description or "").strip() or "暂无描述"
            member_lines.append(f"{friend.name}_{friend.id}: {desc}")
        member_list = "\n".join(member_lines)

        history_query = db.query(GroupMessage).filter(
            GroupMessage.group_id == group_id,
            GroupMessage.message_type == "text"
        )
        if session_id is not None:
            history_query = history_query.filter(GroupMessage.session_id == session_id)
        history_msgs = (
            history_query
            .order_by(GroupMessage.create_time.desc())
            .all()
        )
        history_msgs.reverse()

        history_lines: List[str] = []
        for msg in history_msgs:
            content = (msg.content or "").strip()
            if not content:
                continue
            if msg.sender_type == "friend":
                try:
                    fid = int(msg.sender_id)
                except (ValueError, TypeError):
                    fid = None
                name = friend_map.get(fid).name if fid in friend_map else "未知"
                history_lines.append(f"{name}_{msg.sender_id}: {content}")
            else:
                history_lines.append(f"我: {content}")

        chat_history = "\n".join(history_lines) if history_lines else "(empty)"
        user_prompt = f"当前群成员列表：\n{member_list}\n\n---\n\n当前聊的聊天记录\n{chat_history}"

        logger.info(
            "[GroupManager] Input context for group %s:\nmemberList:\n%s\nchatHistory:\n%s",
            group_id,
            member_list,
            chat_history,
        )

        if not llm_config:
            logger.warning("[GroupManager] LLM config missing, falling back to heuristic selection")
            fallback_ids = GroupChatService._fallback_speaker_ids(history_msgs, friend_map)
            return [friend_map[fid] for fid in fallback_ids if fid in friend_map]

        manager_prompt = get_prompt("chat/group_manager.txt").strip()
        few_shots = GroupChatService._load_manager_few_shots()

        set_agents_default_client(llm_config, use_for_tracing=True)

        raw_model_name = llm_config.model_name
        model_name = llm_service.normalize_model_name(raw_model_name)

        model_settings_kwargs = {}
        if _supports_sampling(model_name):
            model_settings_kwargs["temperature"] = 0.2
            model_settings_kwargs["top_p"] = 0.9
        model_settings = ModelSettings(**model_settings_kwargs)

        use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
        if use_litellm:
            from agents.extensions.models.litellm_model import LitellmModel
            gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
            gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
            agent_model = LitellmModel(model=gemini_model_name, base_url=gemini_base_url, api_key=llm_config.api_key)
        else:
            agent_model = model_name

        agent = Agent(name="GroupManager", instructions=manager_prompt, model=agent_model, model_settings=model_settings)

        try:
            result = await Runner.run(
                agent,
                few_shots + [{"role": "user", "content": user_prompt}],
                run_config=RunConfig(trace_include_sensitive_data=True),
            )
            raw_output = (result.final_output or "").strip()
        except Exception as e:
            logger.error(f"[GroupManager] LLM call failed: {e}")
            fallback_ids = GroupChatService._fallback_speaker_ids(history_msgs, friend_map)
            return [friend_map[fid] for fid in fallback_ids if fid in friend_map]

        parsed_ids = GroupChatService._parse_manager_ids(raw_output)
        if not parsed_ids:
            logger.warning(f"[GroupManager] Empty/invalid output, raw: {raw_output}")
            parsed_ids = GroupChatService._fallback_speaker_ids(history_msgs, friend_map)

        # Filter to valid members and enforce 1~3 speakers
        final_ids: List[int] = []
        seen = set()
        for fid in parsed_ids:
            if fid in friend_map and fid not in seen:
                final_ids.append(fid)
                seen.add(fid)
            if len(final_ids) >= 3:
                break

        if not final_ids:
            final_ids = GroupChatService._fallback_speaker_ids(history_msgs, friend_map)

        logger.info(f"[GroupManager] Selected speakers: {final_ids} (raw={raw_output})")
        return [friend_map[fid] for fid in final_ids if fid in friend_map]

    @staticmethod
    async def send_group_message_stream(
        db: Session,
        group_id: int,
        message_in: group_schemas.GroupMessageCreate,
        sender_id: str = DEFAULT_USER_ID,
        force_new_session: bool = False,
    ) -> AsyncGenerator[dict, None]:
        """
        发送群聊消息并获取 AI 响应。
        支持 @提及 强制触发。
        """
        logger.info(
            "[GroupSmartContext] Incoming group message group=%s force_new_session=%s content_preview=%s",
            group_id,
            force_new_session,
            (message_in.content or "").strip().replace("\n", " ")[:80],
        )
        lock = await _get_group_message_lock(group_id)
        stream = None
        first_event = None

        logger.info("[GroupSmartContext] Waiting lock for group=%s", group_id)
        async with lock:
            logger.info("[GroupSmartContext] Lock acquired for group=%s", group_id)
            if force_new_session:
                reusable_session = GroupChatService._get_active_group_session(db, group_id)
                if reusable_session and _group_session_message_count(db, reusable_session.id) == 0:
                    session = reusable_session
                    logger.info(
                        "[GroupSmartContext] force_new_session=true, reuse existing empty session=%s for group=%s",
                        session.id,
                        group_id,
                    )
                else:
                    session = GroupChatService.create_group_session(db, group_id)
                    logger.info(
                        "[GroupSmartContext] force_new_session=true, skip judgment, created session=%s for group=%s",
                        session.id,
                        group_id,
                    )
            else:
                session = await resolve_session_for_incoming_group_message(
                    db=db,
                    group_id=group_id,
                    current_message=message_in.content,
                )
            logger.info(
                "[GroupSmartContext] Session resolved for group=%s -> session=%s",
                group_id,
                session.id,
            )
            stream = GroupChatService._send_group_message_stream_with_session(
                db=db,
                group_id=group_id,
                session=session,
                message_in=message_in,
                sender_id=sender_id,
            )
            try:
                first_event = await stream.__anext__()
            except StopAsyncIteration:
                logger.warning(
                    "[GroupSmartContext] Stream finished unexpectedly before first event. group=%s session=%s",
                    group_id,
                    session.id,
                )
                return
            logger.info(
                "[GroupSmartContext] First SSE event prepared for group=%s session=%s",
                group_id,
                session.id,
            )

        if first_event:
            yield first_event

        async for event in stream:
            yield event

    @staticmethod
    async def _send_group_message_stream_with_session(
        db: Session,
        group_id: int,
        session: GroupSession,
        message_in: group_schemas.GroupMessageCreate,
        sender_id: str = DEFAULT_USER_ID,
    ) -> AsyncGenerator[dict, None]:
        """
        基于已解析好的 session 进行群聊流式回复。
        """

        # 1. 保存用户消息
        db_message = group_chat_shared.create_user_message(
            db=db,
            group_id=group_id,
            session_id=session.id,
            sender_id=sender_id,
            content=message_in.content,
            message_type=message_in.message_type,
            mentions=message_in.mentions,
        )
        group_chat_shared.touch_session(db, session)

        llm_config = llm_service.get_active_config(db)
        model_name = llm_config.model_name if llm_config else "unknown"

        # 发送起始事件 (FE expects group_id and message_id)
        yield {
            "event": "start", 
            "data": {
                "message_id": db_message.id, 
                "group_id": group_id,
                "session_id": session.id,
                "model": model_name
            }
        }

        # 2. 确定哪些 AI 需要回复
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            yield {"event": "error", "data": {"detail": "Group not found"}}
            return

        participants = []
        friend_map = GroupChatService._get_group_friend_map(db, group_id)
        if message_in.mentions:
            seen = set()
            # 找到被提到的好友（仅限群成员）
            for mention_id in message_in.mentions:
                try:
                    f_id = int(mention_id)
                except (ValueError, TypeError):
                    continue
                if f_id in friend_map and f_id not in seen:
                    participants.append(friend_map[f_id])
                    seen.add(f_id)

        if not participants:
            participants = await GroupChatService._select_speakers_by_manager(
                db=db,
                group_id=group_id,
                session_id=session.id,
                llm_config=llm_config,
                friend_map=friend_map
            )

        if not participants:
            yield {"event": "done", "data": {"message": "No AI responded"}}
            return

        # 2.1 通知前端即将发言的 Agent 列表 (Story 09-10)
        # 将在任何 thinking/message/tool 事件之前发送
        meta_payload = {
            "group_id": group_id,
            "session_id": session.id,
            "participants": [{"id": p.id, "name": p.name} for p in participants]
        }
        yield {"event": "meta_participants", "data": meta_payload}

        # 3. 为每个参与回复的 AI 创建任务
        queue = asyncio.Queue()
        
        # 获取思考模式设置
        enable_thinking = message_in.enable_thinking
        if llm_config and enable_thinking and not llm_config.capability_reasoning:
             # Check if it's gemini (which always has reasoning in some providers but maybe not marked)
             force_thinking = provider_rules.is_gemini_model(llm_config, llm_config.model_name)
             if not force_thinking:
                 enable_thinking = False

        active_tasks = []
        for friend in participants:
            # 为 AI 创建消息占位符
            db_ai_msg = group_chat_shared.create_ai_placeholder(
                db=db,
                group_id=group_id,
                session_id=session.id,
                friend_id=friend.id,
                message_type="text",
            )
            
            task = asyncio.create_task(GroupChatService._run_group_ai_generation_task(
                group_id=group_id,
                session_id=session.id,
                friend_id=friend.id,
                user_msg_id=db_message.id,
                ai_msg_id=db_ai_msg.id,
                message_content=message_in.content,
                enable_thinking=enable_thinking,
                queue=queue
            ))
            active_tasks.append(task)

        # 4. 消费队列中的事件
        completed_count = 0
        while completed_count < len(active_tasks):
            event = await queue.get()
            if event is None: # We use None as a completion signal for ONE task
                completed_count += 1
                continue
            yield event

    @staticmethod
    async def _run_group_ai_generation_task(
        group_id: int,
        session_id: int,
        friend_id: int,
        user_msg_id: int,
        ai_msg_id: int,
        message_content: str,
        enable_thinking: bool,
        queue: asyncio.Queue
    ):
        """
        后台任务：处理单个 AI 在群聊中的生成。
        """
        try:
            with SessionLocal() as db:
                # 1. 获取上下文
                friend = db.query(Friend).filter(Friend.id == friend_id).first()
                if not friend:
                    await queue.put(None)
                    return

                friend_name = friend.name
                
                llm_config = llm_service.get_active_config(db)
                if not llm_config:
                    await queue.put({"event": "error", "data": {"sender_id": str(friend_id), "detail": "LLM Config missing"}})
                    await queue.put(None)
                    return

                raw_model_name = llm_config.model_name
                model_name = llm_service.normalize_model_name(raw_model_name)
                
                # 2. 准备历史记录与召回
                # 获取最近 15 条消息
                history_msgs = group_chat_shared.fetch_group_history(
                    db=db,
                    group_id=group_id,
                    session_id=session_id,
                    before_id=user_msg_id,
                    limit=None,
                )

                # 姓名映射 (用于让 AI 区分谁在说话)
                name_map = group_chat_shared.build_name_map(
                    db=db,
                    messages=history_msgs,
                    default_user_name="我",
                    default_user_id=DEFAULT_USER_ID,
                )
                
                # 记忆召回
                profile_data = ""
                injected_recall_messages = []
                enable_recall = SettingsService.get_setting(db, "memory", "recall_enabled", True)

                if enable_recall:
                    if not embedding_service.get_active_setting(db):
                        logger.warning("[GroupGenTask] Recall skipped: Embedding not configured.")
                        enable_recall = False

                if enable_recall:
                    try:
                        # 获取用户画像
                        from app.services.memo.bridge import MemoService
                        profiles = await MemoService.get_user_profiles(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
                        if profiles and profiles.profiles:
                            profile_lines = [f"- {p.content.strip()}" for p in profiles.profiles if p and p.content]
                            profile_data = "\n".join(profile_lines)
                        
                        # 执行召回
                        from app.services.recall_service import RecallService
                        messages_for_recall = []
                        for m in history_msgs:
                            role = "assistant" if (m.sender_type == "friend" and m.sender_id == str(friend_id)) else "user"
                            messages_for_recall.append({"role": role, "content": m.content})
                        
                        # 增加当前收到的消息参与召回
                        messages_for_recall.append({"role": "user", "content": message_content})

                        recall_result = await RecallService.perform_recall(
                            db, DEFAULT_USER_ID, DEFAULT_SPACE_ID, messages_for_recall, friend_id
                        )
                        injected_recall_messages = recall_result.get("injected_messages", [])
                        
                        # 推送召回的心路历程
                        for fp in recall_result.get("footprints", []):
                            if fp["type"] == "thinking" and enable_thinking:
                                await queue.put({
                                    "event": "recall_thinking", 
                                    "data": {
                                        "sender_id": str(friend_id), 
                                        "delta": f"> {fp['content']}\n"
                                    }
                                })
                            elif fp["type"] == "tool_call":
                                await queue.put({
                                    "event": "tool_call",
                                    "data": {
                                        "sender_id": str(friend_id),
                                        "tool_name": fp["name"],
                                        "arguments": fp["arguments"]
                                    }
                                })
                            elif fp["type"] == "tool_result":
                                await queue.put({
                                    "event": "tool_result",
                                    "data": {
                                        "sender_id": str(friend_id),
                                        "tool_name": fp["name"],
                                        "result": fp["result"]
                                    }
                                })
                    except Exception as e:
                        logger.error(f"[GroupGenTask] Recall failed for {friend_name}: {e}")

                # 3. 构建 Prompt
                beijing_tz = timezone(timedelta(hours=8))
                now_time = datetime.now(timezone.utc).astimezone(beijing_tz)
                weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                current_time = f"{now_time:%Y-%m-%d 约%H}点 {weekday_map[now_time.weekday()]}"
                
                persona_prompt = (friend.system_prompt if friend.system_prompt else get_prompt("chat/default_system_prompt.txt")).strip()
                
                # 注入群聊规则 (Story 09-06)
                try:
                    group_rule = get_prompt("chat/group_chat_rule.txt").strip()
                    
                    # 填充 {memberList}
                    if "{memberList}" in group_rule:
                        all_friends_map = GroupChatService._get_group_friend_map(db, group_id)
                        member_list_parts = []
                        for f in all_friends_map.values():
                            if f.id == friend_id:  # 排除正在发言的自己
                                continue
                            desc = (f.description or "暂无简介").strip()
                            member_list_parts.append(f"{f.name}：{desc}")
                        member_list_str = "\n".join(member_list_parts)
                        group_rule = group_rule.replace("{memberList}", member_list_str)
                    
                    # 填充 {name}
                    if "{name}" in group_rule:
                        group_rule = group_rule.replace("{name}", friend.name)

                    persona_prompt = f"{persona_prompt}\n\n{group_rule}"
                except Exception as e:
                    logger.warning(f"Failed to load group_chat_rule: {e}")

                voice_reply_enabled = bool(friend.enable_voice)
                script_prompt = ""
                if friend.script_expression and not voice_reply_enabled:
                    try: script_prompt = get_prompt("persona/script_expression.txt").strip()
                    except Exception: pass
                    
                segment_prompt = ""
                try:
                    if voice_reply_enabled:
                        segment_prompt = get_prompt("chat/message_segment_tts.txt").strip()
                    elif friend.script_expression:
                        segment_prompt = get_prompt("chat/message_segment_script.txt").strip()
                    else:
                        segment_prompt = get_prompt("chat/message_segment_normal.txt").strip()
                except Exception: pass
                
                try:
                    root_template = get_prompt("chat/root_system_prompt.txt")
                    final_instructions = group_chat_shared.build_system_prompt(
                        root_template=root_template,
                        persona_prompt=persona_prompt,
                        script_prompt=script_prompt,
                        profile_data=profile_data,
                        segment_prompt=segment_prompt,
                        current_time=current_time,
                    )
                except Exception:
                    final_instructions = f"{persona_prompt}\n\n{script_prompt}\n\n{current_time}"

                tool_description = ""
                try:
                    tool_description = get_prompt("recall/recall_tool_description.txt").strip()
                except Exception:
                    pass

                current_other_members = "(empty)"
                mention_result = "被提及，需要发言"

                @function_tool(name_override="recall_memory", description_override=tool_description)
                async def tool_recall(query: str):
                    if not enable_recall:
                        return {"events": []}
                    if not embedding_service.get_active_setting(db):
                        return {"events": []}
                    event_topk = SettingsService.get_setting(db, "memory", "event_topk", 5)
                    threshold = SettingsService.get_setting(db, "memory", "similarity_threshold", 0.5)
                    return await MemoService.recall_memory(
                        user_id=DEFAULT_USER_ID,
                        space_id=DEFAULT_SPACE_ID,
                        query=query,
                        friend_id=friend_id,
                        topk_event=event_topk,
                        threshold=threshold,
                    )

                @function_tool(name_override="get_other_members_messages", description_override="")
                async def tool_get_other_members_messages():
                    return current_other_members

                @function_tool(name_override="is_mentioned", description_override="")
                async def tool_is_mentioned():
                    return mention_result

                # 4. 构建消息列表 (Mock Tool Call 模式 - Story 09-06)
                agent_messages = group_chat_shared.build_group_context(
                    history_msgs=history_msgs,
                    name_map=name_map,
                    self_id=friend_id,
                    current_user_msg=message_content,
                    user_msg_id=user_msg_id,
                    current_other_members=current_other_members,
                    mention_result=mention_result,
                    injected_recall_messages=injected_recall_messages,
                )

                # AC-4: 后端日志中可确认 AI Context 包含格式化的 Tool Result 消息
                logger.info(f"[GroupGenTask] AI Context (Items) for {friend_name} (ID: {friend_id}):\n{json.dumps(agent_messages, ensure_ascii=False, indent=2)}")

                # 6. 调用 LLM
                set_agents_default_client(llm_config, use_for_tracing=True)
                
                temperature = friend.temperature if friend.temperature is not None else 1.0
                top_p = friend.top_p if friend.top_p is not None else 0.9
                
                use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
                model_settings_kwargs = {}
                if _supports_sampling(model_name):
                    model_settings_kwargs["temperature"] = temperature
                    model_settings_kwargs["top_p"] = top_p
                
                if llm_config.capability_reasoning and provider_rules.supports_reasoning_effort(llm_config):
                    model_settings_kwargs["reasoning"] = Reasoning(
                        effort=provider_rules.get_reasoning_effort(
                            llm_config, raw_model_name, enable_thinking
                        )
                    )
                
                model_settings = ModelSettings(**model_settings_kwargs)
                
                if use_litellm:
                    from agents.extensions.models.litellm_model import LitellmModel
                    gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
                    gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
                    agent_model = LitellmModel(model=gemini_model_name, base_url=gemini_base_url, api_key=llm_config.api_key)
                else:
                    agent_model = model_name

                agent_tools = group_chat_shared.build_agent_tools(
                    tool_recall if enable_recall else None,
                    tool_get_other_members_messages,
                    tool_is_mentioned,
                )

                agent = Agent(
                    name=friend.name,
                    instructions=final_instructions,
                    model=agent_model,
                    model_settings=model_settings,
                    tools=agent_tools,
                )
                
                await group_chat_shared.stream_llm_to_queue(
                    agent=agent,
                    agent_messages=agent_messages,
                    queue=queue,
                    enable_thinking=enable_thinking,
                    sender_id=friend_id,
                    message_id=ai_msg_id,
                    session_id=session_id,
                    db=db,
                    sanitize_message_tags=bool(friend.enable_voice),
                )

                # 语音回复（在 done 事件后异步补充 voice 事件）
                if friend.enable_voice:
                    try:
                        final_msg = db.query(GroupMessage).filter(GroupMessage.id == ai_msg_id).first()
                        final_content = (final_msg.content or "") if final_msg else ""

                        async def _on_voice_segment_ready(segment_data: Dict[str, Any]):
                            await queue.put({
                                "event": "voice_segment",
                                "data": {
                                    "sender_id": str(friend_id),
                                    "message_id": ai_msg_id,
                                    "segment": segment_data,
                                },
                            })

                        voice_payload = await generate_voice_payload_for_message(
                            db=db,
                            content=final_content,
                            enable_voice=bool(friend.enable_voice),
                            friend_voice_id=friend.voice_id,
                            message_id=ai_msg_id,
                            message_scope="group",
                            on_segment_ready=_on_voice_segment_ready,
                        )
                        if voice_payload and final_msg:
                            final_msg.voice_payload = voice_payload
                            db.commit()
                            await queue.put({
                                "event": "voice_payload",
                                "data": {
                                    "sender_id": str(friend_id),
                                    "message_id": ai_msg_id,
                                    "voice_payload": voice_payload,
                                },
                            })
                    except Exception as voice_exc:
                        logger.warning("[GroupGenTask] Voice synthesis failed for message=%s: %s", ai_msg_id, voice_exc)



        except Exception as e:
            logger.error(f"[GroupGenTask] Error for {friend_id}: {e}")
            await queue.put({"event": "error", "data": {"sender_id": str(friend_id), "detail": str(e)}})
        finally:
            await queue.put(None) # Signal completion of this producer


    @staticmethod
    def clear_group_messages(db: Session, group_id: int):
        """
        清空群聊消息记录，并同步清除群聊会话。
        """
        db.query(GroupMessage).filter(GroupMessage.group_id == group_id).delete()
        db.query(GroupSession).filter(GroupSession.group_id == group_id).delete()
        db.commit()


group_chat_service = GroupChatService()

