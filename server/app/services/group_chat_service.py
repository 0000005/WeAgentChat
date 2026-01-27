import json
import logging
import asyncio
import re
from typing import List, Optional, AsyncGenerator, Dict
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.models.group import Group, GroupMember, GroupMessage, GroupSession
from app.models.friend import Friend
from app.schemas import group as group_schemas
from app.services.llm_service import llm_service
from app.services.settings_service import SettingsService
from app.services.embedding_service import embedding_service
from app.services import provider_rules
from app.prompt import get_prompt
from app.db.session import SessionLocal
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID


from openai import AsyncOpenAI
from openai.types.shared import Reasoning
from openai.types.responses import (
    ResponseOutputText,
    ResponseTextDeltaEvent,
)
from agents import Agent, ModelSettings, RunConfig, Runner, set_default_openai_client, set_default_openai_api
from agents.items import MessageOutputItem, ReasoningItem, ToolCallItem, ToolCallOutputItem
from agents.stream_events import RunItemStreamEvent

logger = logging.getLogger(__name__)

# Story 09-06: 控制符常量
CTRL_NO_REPLY = "<CTRL:NO_REPLY>"

def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    return model_name.split("/", 1)[-1].lower()

def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")

def _extract_reasoning_text(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw

    def _collect_text(value: object) -> List[str]:
        texts: List[str] = []
        if not value:
            return texts
        if isinstance(value, (list, tuple)):
            for entry in value:
                texts.extend(_collect_text(entry))
            return texts
        if isinstance(value, dict):
            text = value.get("text") or value.get("content")
            if text:
                texts.append(str(text))
            return texts
        text = getattr(value, "text", None) or getattr(value, "content", None)
        if text:
            texts.append(str(text))
        return texts

    if isinstance(raw, dict):
        text = raw.get("reasoning_content") or raw.get("reasoning") or raw.get("text")
        if text:
            return str(text)
        content = raw.get("content")
        summary = raw.get("summary")
    else:
        text = getattr(raw, "reasoning_content", None) or getattr(raw, "reasoning", None) or getattr(raw, "text", None)
        if text:
            return str(text)
        content = getattr(raw, "content", None)
        summary = getattr(raw, "summary", None)

    texts = _collect_text(content)
    if not texts:
        texts = _collect_text(summary)
    return "\n".join([t for t in texts if t])

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
            .filter(GroupSession.group_id == group_id, GroupSession.ended == False)
            .order_by(GroupSession.id.desc())
            .first()
        )

    @staticmethod
    def _create_group_session(db: Session, group_id: int, title: Optional[str] = None) -> GroupSession:
        session = GroupSession(group_id=group_id, title=title or "群聊会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

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
        active_sessions = (
            db.query(GroupSession)
            .filter(GroupSession.group_id == group_id, GroupSession.ended == False)
            .all()
        )
        if active_sessions:
            now_time = datetime.now(timezone.utc)
            for session in active_sessions:
                logger.info(f"[GroupSession] Manual new session: Ending session {session.id}. (NO memory extraction - group chat policy)")
                session.ended = True
                session.update_time = now_time
            db.commit()
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
            .limit(20)
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

        client = AsyncOpenAI(base_url=llm_config.base_url, api_key=llm_config.api_key)
        set_default_openai_client(client, use_for_tracing=True)
        set_default_openai_api("chat_completions")

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
        sender_id: str = DEFAULT_USER_ID
    ) -> AsyncGenerator[dict, None]:
        """
        发送群聊消息并获取 AI 响应。
        支持 @提及 强制触发。
        """
        # 0. 获取或创建群聊会话
        session = GroupChatService.get_or_create_session_for_group(db, group_id)

        # 1. 保存用户消息
        db_message = GroupMessage(
            group_id=group_id,
            session_id=session.id,
            sender_id=sender_id,
            sender_type="user",
            content=message_in.content,
            message_type=message_in.message_type,
            mentions=message_in.mentions
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        now_time = datetime.now(timezone.utc)
        session.last_message_time = now_time
        session.update_time = now_time
        db.commit()

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
            db_ai_msg = GroupMessage(
                group_id=group_id,
                session_id=session.id,
                sender_id=str(friend.id),
                sender_type="friend",
                content="",
                message_type="text"
            )
            db.add(db_ai_msg)
            db.commit()
            db.refresh(db_ai_msg)
            
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
                history_msgs = (
                    db.query(GroupMessage)
                    .filter(
                        GroupMessage.group_id == group_id,
                        GroupMessage.session_id == session_id,
                        GroupMessage.id < user_msg_id
                    )
                    .order_by(GroupMessage.create_time.desc())
                    .limit(15)
                    .all()
                )
                history_msgs.reverse()
                
                # 姓名映射 (用于让 AI 区分谁在说话)
                member_ids = {msg.sender_id for msg in history_msgs}
                f_ids = []
                for mid in member_ids:
                    try: f_ids.append(int(mid))
                    except (ValueError, TypeError): continue
                
                friends_data = db.query(Friend).filter(Friend.id.in_(f_ids)).all()
                name_map = {str(f.id): f.name for f in friends_data}
                name_map[DEFAULT_USER_ID] = "我"
                
                # 记忆召回
                profile_data = ""
                injected_recall_messages = []
                enable_recall = SettingsService.get_setting(db, "memory", "recall_enabled", True)
                
                if enable_recall and embedding_service.get_active_setting(db):
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
                    persona_prompt = f"{persona_prompt}\n\n{group_rule}"
                except Exception as e:
                    logger.warning(f"Failed to load group_chat_rule: {e}")

                script_prompt = ""
                if friend.script_expression:
                    try: script_prompt = get_prompt("persona/script_expression.txt").strip()
                    except Exception: pass
                    
                segment_prompt = ""
                try:
                    if friend.script_expression:
                        segment_prompt = get_prompt("chat/message_segment_script.txt").strip()
                    else:
                        segment_prompt = get_prompt("chat/message_segment_normal.txt").strip()
                except Exception: pass
                
                try:
                    root_template = get_prompt("chat/root_system_prompt.txt")
                    # 群聊特有的上下文提示
                    group_context = f"\n\n你现在在群聊中，你的名字是 {friend.name}。只有被@时才发言，其他时候保持沉默并输出 {CTRL_NO_REPLY}。"
                    
                    final_instructions = root_template.replace("{{role-play-prompt}}", persona_prompt + group_context)
                    final_instructions = final_instructions.replace("{{script-expression}}", f"\n\n{script_prompt}" if script_prompt else "")
                    final_instructions = final_instructions.replace("{{user-profile}}", f"\n\n【用户信息】\n{profile_data}" if profile_data else "")
                    final_instructions = final_instructions.replace("{{segment-instruction}}", f"\n\n{segment_prompt}" if segment_prompt else "")
                    final_instructions = final_instructions.replace("{{current-time}}", current_time)
                except Exception:
                    final_instructions = f"{persona_prompt}\n\n{script_prompt}\n\n{current_time}"

                # 4. 构建消息列表 (Mock Tool Call 模式 - Story 09-06)
                agent_messages = []
                
                # 将历史记录切分为以“人类消息”开头的轮次
                rounds = []
                current_round = None
                
                for msg in history_msgs:
                    if msg.sender_type == "user":
                        if current_round:
                            rounds.append(current_round)
                        current_round = {"user": msg, "others": [], "self": None}
                    else:
                        if current_round:
                            if msg.sender_type == "friend" and msg.sender_id == str(friend_id):
                                current_round["self"] = msg
                            else:
                                current_round["others"].append(msg)
                        else:
                            # 历史开头的非用户消息，先忽略或归入虚拟轮次
                            pass
                if current_round:
                    rounds.append(current_round)

                # 转换为上帝视角格式（使用 Agents Item 格式）
                for r in rounds:
                    u_msg = r["user"]
                    agent_messages.append({"role": "user", "content": u_msg.content})
                    
                    # 虚拟工具 Item：获取其他成员发言
                    others_content = "\n".join([f"{name_map.get(m.sender_id, '未知')}: {m.content}" for m in r["others"]])
                    if not others_content:
                        others_content = "(empty)"
                    
                    tc_id_hist = f"call_get_msgs_{u_msg.id}"
                    agent_messages.append({
                        "type": "function_call",
                        "call_id": tc_id_hist,
                        "name": "get_other_members_messages",
                        "arguments": "{}"
                    })
                    agent_messages.append({
                        "type": "function_call_output",
                        "call_id": tc_id_hist,
                        "output": others_content
                    })
                    
                    # 补齐发言历史 Item
                    if r["self"] and r["self"].content.strip():
                        agent_messages.append({"role": "assistant", "content": r["self"].content})
                    else:
                        agent_messages.append({"role": "assistant", "content": CTRL_NO_REPLY})
                
                # 注入召回信息 (保持在当前消息前)
                if injected_recall_messages:
                    # 允许注入全部 Item (包括 function_call/function_call_output)
                    agent_messages.extend(injected_recall_messages)
                
                # 5. 当前轮次注入
                agent_messages.append({"role": "user", "content": message_content})
                
                # 注入当前轮次的 Mock 工具调用 Item
                # get_other_members_messages
                tc_id_curr = f"call_curr_msgs_{user_msg_id}"
                agent_messages.append({
                    "type": "function_call",
                    "call_id": tc_id_curr,
                    "name": "get_other_members_messages",
                    "arguments": "{}"
                })
                agent_messages.append({
                    "type": "function_call_output",
                    "call_id": tc_id_curr,
                    "output": "(empty)" # 并行执行时，尚未有其他 AI 回复
                })
                
                # is_mentioned
                tc_id_ment = f"call_ment_{user_msg_id}"
                agent_messages.append({
                    "type": "function_call",
                    "call_id": tc_id_ment,
                    "name": "is_mentioned",
                    "arguments": "{}"
                })
                agent_messages.append({
                    "type": "function_call_output",
                    "call_id": tc_id_ment,
                    "output": "被提及，需要发言"
                })

                # AC-4: 后端日志中可确认 AI Context 包含格式化的 Tool Result 消息
                logger.info(f"[GroupGenTask] AI Context (Items) for {friend_name} (ID: {friend_id}):\n{json.dumps(agent_messages, ensure_ascii=False, indent=2)}")

                # 6. 调用 LLM
                client = AsyncOpenAI(base_url=llm_config.base_url, api_key=llm_config.api_key)
                set_default_openai_client(client)
                
                temperature = friend.temperature if friend.temperature is not None else 0.8
                top_p = friend.top_p if friend.top_p is not None else 0.9
                
                use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
                model_settings_kwargs = {}
                if _supports_sampling(model_name):
                    model_settings_kwargs["temperature"] = temperature
                    model_settings_kwargs["top_p"] = top_p
                
                if llm_config.capability_reasoning and provider_rules.supports_reasoning_effort(llm_config):
                    model_settings_kwargs["reasoning"] = Reasoning(effort="low" if enable_thinking else "none")
                
                model_settings = ModelSettings(**model_settings_kwargs)
                
                if use_litellm:
                    from agents.extensions.models.litellm_model import LitellmModel
                    gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
                    gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
                    agent_model = LitellmModel(model=gemini_model_name, base_url=gemini_base_url, api_key=llm_config.api_key)
                else:
                    agent_model = model_name

                agent = Agent(name=friend.name, instructions=final_instructions, model=agent_model, model_settings=model_settings)
                
                content_buffer = ""
                has_reasoning_item = False
                tool_call_names = {}
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                
                result = Runner.run_streamed(agent, agent_messages, run_config=RunConfig(trace_include_sensitive_data=True))
                
                # 定义解析工具函数（如果当前作用域没有定义）
                def _internal_extract_reasoning(raw: object) -> str:
                    if raw is None: return ""
                    if isinstance(raw, str): return raw
                    # 简化地提取 text/content
                    if isinstance(raw, dict):
                        return str(raw.get("reasoning_content") or raw.get("reasoning") or raw.get("text") or raw.get("content") or "")
                    else:
                        return str(getattr(raw, "reasoning_content", None) or getattr(raw, "reasoning", None) or getattr(raw, "text", None) or getattr(raw, "content", None) or "")


                buffer = ""
                is_thinking_tag = False
                think_fallback_buffer = ""
                THINK_START = "<think>"
                THINK_END = "</think>"
                saved_content = ""

                async for event in result.stream_events():
                    # 处理思考过程 (DeepSeek reason_item)
                    if isinstance(event, RunItemStreamEvent) and event.name == "reasoning_item_created":
                        if enable_thinking and isinstance(event.item, ReasoningItem):
                            has_reasoning_item = True
                            raw = event.item.raw_item
                            text = _internal_extract_reasoning(raw)
                            if text:
                                await queue.put({
                                    "event": "model_thinking", 
                                    "data": {
                                        "sender_id": str(friend_id),
                                        "delta": text,
                                        "message_id": ai_msg_id
                                    }
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
                                    "sender_id": str(friend_id),
                                    "tool_name": name or "tool",
                                    "arguments": arguments,
                                    "call_id": call_id,
                                    "message_id": ai_msg_id
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
                                    "sender_id": str(friend_id),
                                    "tool_name": name,
                                    "result": event.item.output,
                                    "call_id": call_id,
                                    "message_id": ai_msg_id
                                },
                            })
                        continue
                    
                    # 处理文本内容
                    if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                        delta = event.data.delta
                        if delta:
                            content_buffer += delta
                            # 处理 <think> 标签逻辑
                            buffer += delta
                            
                            while buffer:
                                if not is_thinking_tag:
                                    start_idx = buffer.find(THINK_START)
                                    if start_idx != -1:
                                        # 发现开始标签前的内容为正文
                                        if start_idx > 0:
                                            msg_delta = buffer[:start_idx]
                                            saved_content += msg_delta
                                            await queue.put({
                                                "event": "message",
                                                "data": {
                                                    "sender_id": str(friend_id),
                                                    "delta": msg_delta,
                                                    "message_id": ai_msg_id
                                                }
                                            })
                                        buffer = buffer[start_idx + len(THINK_START):]
                                        is_thinking_tag = True
                                    else:
                                        # 没有开始标签
                                        if "<" not in buffer:
                                            # 安全，全部输出
                                            saved_content += buffer
                                            await queue.put({
                                                "event": "message",
                                                "data": {
                                                    "sender_id": str(friend_id),
                                                    "delta": buffer,
                                                    "message_id": ai_msg_id
                                                }
                                            })
                                            buffer = ""
                                        else:
                                            # 可能有标签，等待更多字符
                                            break
                                else:
                                    # 在思考标签内
                                    end_idx = buffer.find(THINK_END)
                                    if end_idx != -1:
                                        # 发现结束标签
                                        if end_idx > 0 and enable_thinking and not has_reasoning_item:
                                            think_chunk = buffer[:end_idx]
                                            think_fallback_buffer += think_chunk
                                            await queue.put({
                                                "event": "model_thinking",
                                                "data": {
                                                    "sender_id": str(friend_id),
                                                    "delta": think_chunk,
                                                    "message_id": ai_msg_id
                                                }
                                            })
                                        
                                        buffer = buffer[end_idx + len(THINK_END):]
                                        is_thinking_tag = False
                                    else:
                                        # 没发现结束标签
                                        if "</" not in buffer:
                                            if enable_thinking and not has_reasoning_item:
                                                think_fallback_buffer += buffer
                                                await queue.put({
                                                    "event": "model_thinking",
                                                    "data": {
                                                        "sender_id": str(friend_id),
                                                        "delta": buffer,
                                                        "message_id": ai_msg_id
                                                    }
                                                })
                                            buffer = ""
                                        else:
                                            break

                
                # 处理剩余 buffer
                if buffer:
                    if is_thinking_tag:
                        if enable_thinking and not has_reasoning_item:
                            think_fallback_buffer += buffer
                            await queue.put({
                                "event": "model_thinking",
                                "data": {
                                    "sender_id": str(friend_id),
                                    "delta": buffer,
                                    "message_id": ai_msg_id
                                }
                            })
                    else:
                        saved_content += buffer
                        await queue.put({
                            "event": "message",
                            "data": {
                                "sender_id": str(friend_id),
                                "delta": buffer,
                                "message_id": ai_msg_id
                            }
                        })

                
                # 最后如果只使用了 content_buffer 但经过过滤后 saved_content 为空且也没提取到思考内容
                # 说明可能全被当做 content 了，或者 content_buffer 就是最终纯文本
                # 在此为了保险，持久化时使用 content_buffer (包含所有原文)，或者 saved_content (仅正文)
                # 通常我们希望存纯净的正文到 content 字段，思考过程可以放另一字段或者直接不存(目前模型没此字段)
                # 这里为了保持一致，我们优先使用 filter 后的正文作为 content
                
                final_content = saved_content if saved_content else content_buffer
                # 去除可能残余的标签
                final_content = final_content.replace(THINK_START, "").replace(THINK_END, "")


                # 6. 持久化
                db_msg = db.query(GroupMessage).filter(GroupMessage.id == ai_msg_id).first()
                if db_msg:
                    db_msg.content = final_content
                    db.commit()
                    group_session = db.query(GroupSession).filter(GroupSession.id == session_id).first()
                    if group_session:
                        now_time = datetime.now(timezone.utc)
                        group_session.last_message_time = now_time
                        group_session.update_time = now_time
                        db.commit()

                usage["completion_tokens"] = len(content_buffer)
                # 发送完成事件
                await queue.put({
                    "event": "done", 
                    "data": {
                        "sender_id": str(friend_id),
                        "message_id": ai_msg_id,
                        "session_id": session_id,
                        "content": final_content,
                        "usage": usage
                    }
                })



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

