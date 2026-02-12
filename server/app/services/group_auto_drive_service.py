import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, AsyncGenerator, Tuple

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.friend import Friend
from app.models.group import GroupMember, GroupMessage, GroupSession, GroupAutoDriveRun
from app.prompt import get_prompt
from app.schemas import group_auto_drive as ad_schemas
from app.services import group_chat_shared, provider_rules
from app.services.llm_service import llm_service
from app.services.memo.constants import DEFAULT_USER_ID
from app.services.llm_client import set_agents_default_client
from app.services.voice_message_service import generate_voice_payload_for_message

from openai.types.shared import Reasoning
from agents import Agent, ModelSettings, function_tool

logger = logging.getLogger(__name__)


def _model_base_name(model_name: Optional[str]) -> str:
    if not model_name:
        return ""
    return model_name.split("/", 1)[-1].lower()


def _supports_sampling(model_name: Optional[str]) -> bool:
    return not _model_base_name(model_name).startswith("gpt-5")


@dataclass
class AutoDriveRuntime:
    run_id: int
    group_id: int
    session_id: int
    enable_thinking: bool
    queue: asyncio.Queue
    pause_event: asyncio.Event
    stop_event: asyncio.Event
    pause_requested: bool = False
    task: Optional[asyncio.Task] = None


class GroupAutoDriveService:
    def __init__(self) -> None:
        self._runtimes: Dict[int, AutoDriveRuntime] = {}

    def _get_group_friend_map(self, db: Session, group_id: int) -> Dict[str, Friend]:
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

        friends = db.query(Friend).filter(Friend.id.in_(friend_ids), Friend.deleted == False).all()
        return {str(f.id): f for f in friends}

    def _normalize_roles(
        self,
        config: ad_schemas.AutoDriveConfig,
    ) -> Tuple[Dict, Dict[str, str], List[str]]:
        roles = config.roles or {}
        side_map: Dict[str, str] = {}
        order: List[str] = []

        def _clean_list(values: List) -> List[str]:
            cleaned: List[str] = []
            for val in values:
                sval = str(val).strip()
                if sval and sval not in cleaned:
                    cleaned.append(sval)
            return cleaned

        if config.mode in ("brainstorm", "decision"):
            participants = _clean_list(roles.get("participants") or roles.get("参与成员") or [])
            order = participants
            roles = {**roles, "participants": participants}
            return roles, side_map, order

        affirmative = _clean_list(roles.get("affirmative") or roles.get("正方") or [])
        negative = _clean_list(roles.get("negative") or roles.get("反方") or [])
        affirmative_sorted = sorted(affirmative, key=lambda x: x)
        negative_sorted = sorted(negative, key=lambda x: x)
        for aid in affirmative_sorted:
            side_map[aid] = "affirmative"
        for nid in negative_sorted:
            side_map[nid] = "negative"
        order = []
        for idx in range(min(len(affirmative_sorted), len(negative_sorted))):
            order.append(affirmative_sorted[idx])
            order.append(negative_sorted[idx])

        roles = {
            **roles,
            "affirmative": affirmative_sorted,
            "negative": negative_sorted,
            "order": order,
        }
        return roles, side_map, order

    def _format_topic(self, config: ad_schemas.AutoDriveConfig) -> Dict[str, str]:
        topic = config.topic or {}

        def _pick(*keys: str) -> str:
            for key in keys:
                val = topic.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            return ""

        if config.mode == "brainstorm":
            return {
                "theme": _pick("theme", "主题", "topic"),
                "goal": _pick("goal", "目标"),
                "constraints": _pick("constraints", "约束"),
            }
        if config.mode == "decision":
            options = topic.get("options") or topic.get("候选方案") or topic.get("candidate_options") or ""
            if isinstance(options, list):
                options = "\n".join([str(o) for o in options if str(o).strip()])
            return {
                "question": _pick("question", "决策问题"),
                "options": str(options),
                "criteria": _pick("criteria", "评估标准"),
            }
        return {
            "motion": _pick("motion", "辩题"),
            "affirmative": _pick("affirmative", "正方立场"),
            "negative": _pick("negative", "反方立场"),
        }

    def _phase_label(self, mode: str, phase: str) -> str:
        mapping = {
            "brainstorm": {
                "opening": "开场设定",
                "rounds": "轮次推进",
                "summary": "收敛整理",
            },
            "decision": {
                "opening": "开场设定",
                "rounds": "方案分析",
                "summary": "推荐与落地",
            },
            "debate": {
                "opening": "立论陈述",
                "free": "自由交锋",
                "summary": "总结陈词",
                "judge": "评委宣判",
            },
        }
        return mapping.get(mode, {}).get(phase, phase)

    def _build_auto_drive_rule(self, mode: str, phase: str, round_no: int) -> str:
        try:
            rule = get_prompt("auto_drive/auto_drive_rule.txt").strip()
        except Exception:
            return ""
        rule = rule.replace("{auto_drive_mode}", mode)
        rule = rule.replace("{auto_drive_phase}", self._phase_label(mode, phase))
        rule = rule.replace("{auto_drive_round}", str(round_no))
        return rule

    def _build_host_message(
        self,
        mode: str,
        phase: str,
        round_no: int,
        speaker_name: str,
        topic: Dict[str, str],
        side: Optional[str] = None,
    ) -> str:
        if mode == "brainstorm":
            if phase == "opening":
                return (
                    f"本次头脑风暴主题是：{topic.get('theme')}。"
                    f"目标是：{topic.get('goal')}。"
                    f"约束是：{topic.get('constraints')}。"
                    f"第 {round_no} 轮开始，@{speaker_name} 请发言。"
                )
            if phase == "summary":
                return f"@{speaker_name}，请做本次头脑风暴总结（创意清单 + 归类/合并 + Top 结论）。"
            return f"第 {round_no} 轮开始，@{speaker_name} 请发言。"

        if mode == "decision":
            if phase == "opening":
                return (
                    f"本次决策问题是：{topic.get('question')}。"
                    f"候选方案如下：{topic.get('options')}。"
                    f"评估标准是：{topic.get('criteria')}。"
                    f"第 {round_no} 轮开始，@{speaker_name} 请发言。"
                )
            if phase == "summary":
                return f"@{speaker_name}，请做最终决策总结（方案对比 + 推荐方案 + 风险与下一步）。"
            return f"第 {round_no} 轮开始，@{speaker_name} 请发言。"

        if phase == "opening":
            return (
                f"辩题是：{topic.get('motion')}。"
                f"正方观点：{topic.get('affirmative')}。"
                f"反方观点：{topic.get('negative')}。"
                f"辩论开始，先由正方 @{speaker_name} 陈述核心观点。"
            )

        if phase == "statement":
            if side == "affirmative":
                return f"正方 @{speaker_name}，请陈述核心观点。"
            return f"反方 @{speaker_name}，请陈述核心观点。"

        if phase == "free":
            return f"自由交锋阶段，@{speaker_name} 请发言。"

        if phase == "summary":
            if side == "negative":
                return f"反方总结，@{speaker_name} 请发言。"
            return f"正方总结，@{speaker_name} 请发言。"

        if phase == "judge":
            return f"评委 @{speaker_name} 请宣布胜负并给出理由。"

        return f"@{speaker_name} 请发言。"

    def _state_payload(self, run: GroupAutoDriveRun) -> dict:
        started_at = run.started_at.isoformat() if run.started_at else None
        ended_at = run.ended_at.isoformat() if run.ended_at else None
        return {
            "run_id": run.id,
            "group_id": run.group_id,
            "session_id": run.session_id,
            "mode": run.mode,
            "status": run.status,
            "phase": run.phase,
            "current_round": run.current_round,
            "current_turn": run.current_turn,
            "next_speaker_id": run.next_speaker_id,
            "pause_reason": run.pause_reason,
            "started_at": started_at,
            "ended_at": ended_at,
            "topic": run.topic_json,
            "roles": run.roles_json,
            "turn_limit": run.turn_limit,
            "end_action": run.end_action,
            "judge_id": run.judge_id,
            "summary_by": run.summary_by,
        }

    def _to_state_read(self, run: GroupAutoDriveRun) -> ad_schemas.AutoDriveStateRead:
        return ad_schemas.AutoDriveStateRead(**self._state_payload(run))

    def _get_active_run(self, db: Session, group_id: int) -> Optional[GroupAutoDriveRun]:
        return (
            db.query(GroupAutoDriveRun)
            .filter(
                GroupAutoDriveRun.group_id == group_id,
                GroupAutoDriveRun.status.in_(["running", "paused", "pausing"]),
            )
            .order_by(GroupAutoDriveRun.id.desc())
            .first()
        )

    async def start_auto_drive(
        self,
        db: Session,
        group_id: int,
        config: ad_schemas.AutoDriveConfig,
        enable_thinking: bool = False,
    ) -> ad_schemas.AutoDriveStateRead:
        existing = self._get_active_run(db, group_id)
        if existing:
            raise ValueError("当前群聊已有自驱任务在运行")

        roles_json, _, _ = self._normalize_roles(config)

        session_title = f"自驱-{config.mode}"
        group_chat_shared.end_active_sessions(db, group_id, session_type=config.mode)
        session = group_chat_shared.create_group_session(
            db,
            group_id,
            title=session_title,
            session_type=config.mode,
        )

        now_time = datetime.now(timezone.utc)
        run = GroupAutoDriveRun(
            group_id=group_id,
            session_id=session.id,
            mode=config.mode,
            topic_json=config.topic,
            roles_json=roles_json,
            turn_limit=config.turn_limit,
            end_action=config.end_action,
            judge_id=config.judge_id,
            summary_by=config.summary_by,
            status="running",
            phase="opening" if config.mode == "debate" else "rounds",
            current_round=0,
            current_turn=0,
            next_speaker_id=None,
            pause_reason=None,
            started_at=now_time,
            create_time=now_time,
            update_time=now_time,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        runtime = AutoDriveRuntime(
            run_id=run.id,
            group_id=group_id,
            session_id=session.id,
            enable_thinking=enable_thinking,
            queue=asyncio.Queue(),
            pause_event=asyncio.Event(),
            stop_event=asyncio.Event(),
        )
        runtime.pause_event.set()
        runtime.task = asyncio.create_task(self._run_auto_drive_loop(run.id))
        self._runtimes[group_id] = runtime

        await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})

        return self._to_state_read(run)

    async def stream_auto_drive(self, group_id: int) -> AsyncGenerator[dict, None]:
        runtime = self._runtimes.get(group_id)
        if not runtime:
            yield {"event": "auto_drive_error", "data": {"detail": "No active auto-drive"}}
            return

        while True:
            event = await runtime.queue.get()
            if event is None:
                break
            yield event

    async def pause_auto_drive(self, db: Session, group_id: int) -> ad_schemas.AutoDriveStateRead:
        run = self._get_active_run(db, group_id)
        if not run:
            raise ValueError("未找到运行中的自驱任务")

        run.status = "pausing"
        run.pause_reason = "等待收尾"
        run.update_time = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

        runtime = self._runtimes.get(group_id)
        if runtime:
            runtime.pause_requested = True
            await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})

        return self._to_state_read(run)

    async def resume_auto_drive(self, db: Session, group_id: int) -> ad_schemas.AutoDriveStateRead:
        run = self._get_active_run(db, group_id)
        if not run:
            raise ValueError("未找到运行中的自驱任务")

        run.status = "running"
        run.pause_reason = None
        run.update_time = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)

        runtime = self._runtimes.get(group_id)
        if runtime:
            # 清掉挂起的暂停请求，避免恢复后再次被下一次检查拉回暂停态
            runtime.pause_requested = False
            runtime.pause_event.set()
            await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})

        return self._to_state_read(run)

    async def stop_auto_drive(self, db: Session, group_id: int) -> ad_schemas.AutoDriveStateRead:
        run = self._get_active_run(db, group_id)
        if not run:
            raise ValueError("未找到运行中的自驱任务")

        run.status = "ended"
        run.ended_at = datetime.now(timezone.utc)
        run.update_time = run.ended_at
        db.commit()
        db.refresh(run)

        runtime = self._runtimes.get(group_id)
        if runtime:
            runtime.stop_event.set()
            runtime.pause_event.set()
            await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})

        return self._to_state_read(run)

    def get_state(self, db: Session, group_id: int) -> Optional[ad_schemas.AutoDriveStateRead]:
        run = self._get_active_run(db, group_id)
        if not run:
            return None
        return self._to_state_read(run)

    async def _run_auto_drive_loop(self, run_id: int) -> None:
        try:
            with SessionLocal() as db:
                run = db.query(GroupAutoDriveRun).filter(GroupAutoDriveRun.id == run_id).first()
                if not run:
                    return
                group_id = run.group_id
                runtime = self._runtimes.get(group_id)
                if not runtime:
                    return

                config = ad_schemas.AutoDriveConfig(
                    mode=run.mode,
                    topic=run.topic_json or {},
                    roles=run.roles_json or {},
                    turn_limit=run.turn_limit,
                    end_action=run.end_action,
                    judge_id=run.judge_id,
                    summary_by=run.summary_by,
                )

                roles_json, side_map, order = self._normalize_roles(config)
                run.roles_json = roles_json
                db.commit()
                db.refresh(run)

                friend_map = self._get_group_friend_map(db, group_id)
                if not friend_map:
                    await runtime.queue.put({"event": "auto_drive_error", "data": {"detail": "群内无可用成员"}})
                    return

                for member_id in order:
                    if member_id not in friend_map:
                        await runtime.queue.put({"event": "auto_drive_error", "data": {"detail": f"成员 {member_id} 不在群内"}})
                        return

                topic = self._format_topic(config)

                if config.mode == "debate":
                    await self._run_debate_mode(db, runtime, run, config, topic, side_map, order, friend_map)
                else:
                    await self._run_round_mode(db, runtime, run, config, topic, order, friend_map)

        except Exception as e:
            logger.error(f"[AutoDrive] Runner failed: {e}")
            runtime = None
            if run_id:
                for r in self._runtimes.values():
                    if r.run_id == run_id:
                        runtime = r
                        break
            if runtime:
                await runtime.queue.put({"event": "auto_drive_error", "data": {"detail": str(e)}})
        finally:
            await self._ensure_run_closed(run_id)
            await self._finalize_runtime(run_id)

    async def _run_round_mode(
        self,
        db: Session,
        runtime: AutoDriveRuntime,
        run: GroupAutoDriveRun,
        config: ad_schemas.AutoDriveConfig,
        topic: Dict[str, str],
        order: List[str],
        friend_map: Dict[str, Friend],
    ) -> None:
        total_rounds = config.turn_limit
        current_turn = run.current_turn

        for round_no in range(1, total_rounds + 1):
            round_msgs: List[GroupMessage] = []
            for idx, member_id in enumerate(order):
                if not await self._wait_if_paused(db, runtime, run):
                    return

                friend = friend_map[member_id]
                phase = "opening" if round_no == 1 and idx == 0 else "rounds"
                speaker_name = friend.name
                host_message = self._build_host_message(
                    config.mode,
                    phase,
                    round_no,
                    speaker_name,
                    topic,
                )
                current_turn += 1
                await self._update_state(
                    db,
                    runtime,
                    run,
                    status="running",
                    phase=phase if phase != "rounds" else "rounds",
                    current_round=round_no,
                    current_turn=current_turn,
                    next_speaker_id=member_id,
                    pause_reason=None,
                )

                other_text = group_chat_shared.build_other_members_text(round_msgs, group_chat_shared.build_name_map(db, round_msgs))
                await self._dispatch_speaker(
                    db,
                    runtime,
                    run,
                    friend,
                    host_message,
                    member_id,
                    other_text,
                    debate_side=None,
                )

                refreshed = db.query(GroupMessage).filter(GroupMessage.session_id == run.session_id, GroupMessage.sender_id == member_id).order_by(GroupMessage.id.desc()).first()
                if refreshed:
                    round_msgs.append(refreshed)

            run.current_round = round_no
            db.commit()
            db.refresh(run)

        if config.end_action in ("summary", "both"):
            summary_by = config.summary_by
            if summary_by and summary_by != DEFAULT_USER_ID:
                friend = friend_map.get(str(summary_by))
                if friend:
                    current_turn += 1
                    await self._update_state(
                        db,
                        runtime,
                        run,
                        status="running",
                        phase="summary",
                        current_round=run.current_round,
                        current_turn=current_turn,
                        next_speaker_id=str(summary_by),
                        pause_reason=None,
                    )
                    host_message = self._build_host_message(
                        config.mode,
                        "summary",
                        run.current_round or total_rounds,
                        friend.name,
                        topic,
                    )
                    await self._dispatch_speaker(
                        db,
                        runtime,
                        run,
                        friend,
                        host_message,
                        str(summary_by),
                        "(empty)",
                        debate_side=None,
                    )

        await self._end_run(db, runtime, run)

    async def _run_debate_mode(
        self,
        db: Session,
        runtime: AutoDriveRuntime,
        run: GroupAutoDriveRun,
        config: ad_schemas.AutoDriveConfig,
        topic: Dict[str, str],
        side_map: Dict[str, str],
        order: List[str],
        friend_map: Dict[str, Friend],
    ) -> None:
        current_turn = run.current_turn
        affirmative = run.roles_json.get("affirmative", [])
        negative = run.roles_json.get("negative", [])

        if not affirmative or not negative:
            await runtime.queue.put({"event": "auto_drive_error", "data": {"detail": "正反方配置缺失"}})
            return

        opening_order = [affirmative[0], negative[0]]
        for idx, member_id in enumerate(opening_order):
            if not await self._wait_if_paused(db, runtime, run):
                return
            friend = friend_map[member_id]
            phase = "opening" if idx == 0 else "statement"
            current_turn += 1
            await self._update_state(
                db,
                runtime,
                run,
                status="running",
                phase="opening",
                current_round=0,
                current_turn=current_turn,
                next_speaker_id=member_id,
                pause_reason=None,
            )
            host_message = self._build_host_message(
                "debate",
                phase,
                0,
                friend.name,
                topic,
                side_map.get(member_id),
            )
            await self._dispatch_speaker(
                db,
                runtime,
                run,
                friend,
                host_message,
                member_id,
                "(empty)",
                debate_side=side_map.get(member_id),
            )

        total_rounds = config.turn_limit
        for round_no in range(1, total_rounds + 1):
            round_msgs: List[GroupMessage] = []
            for member_id in order:
                if not await self._wait_if_paused(db, runtime, run):
                    return
                friend = friend_map[member_id]
                current_turn += 1
                await self._update_state(
                    db,
                    runtime,
                    run,
                    status="running",
                    phase="free",
                    current_round=round_no,
                    current_turn=current_turn,
                    next_speaker_id=member_id,
                    pause_reason=None,
                )
                other_text = group_chat_shared.build_other_members_text(round_msgs, group_chat_shared.build_name_map(db, round_msgs))
                host_message = self._build_host_message(
                    "debate",
                    "free",
                    round_no,
                    friend.name,
                    topic,
                    side_map.get(member_id),
                )
                await self._dispatch_speaker(
                    db,
                    runtime,
                    run,
                    friend,
                    host_message,
                    member_id,
                    other_text,
                    debate_side=side_map.get(member_id),
                )
                refreshed = db.query(GroupMessage).filter(
                    GroupMessage.session_id == run.session_id,
                    GroupMessage.sender_id == member_id,
                ).order_by(GroupMessage.id.desc()).first()
                if refreshed:
                    round_msgs.append(refreshed)

            run.current_round = round_no
            db.commit()
            db.refresh(run)

        # 辩论必须包含总结陈词阶段
        summary_order = [negative[0], affirmative[0]]
        for member_id in summary_order:
            if not await self._wait_if_paused(db, runtime, run):
                return
            friend = friend_map[member_id]
            current_turn += 1
            await self._update_state(
                db,
                runtime,
                run,
                status="running",
                phase="summary",
                current_round=run.current_round,
                current_turn=current_turn,
                next_speaker_id=member_id,
                pause_reason=None,
            )
            host_message = self._build_host_message(
                "debate",
                "summary",
                run.current_round,
                friend.name,
                topic,
                side_map.get(member_id),
            )
            await self._dispatch_speaker(
                db,
                runtime,
                run,
                friend,
                host_message,
                member_id,
                "(empty)",
                debate_side=side_map.get(member_id),
            )

        if config.end_action in ("judge", "both") and config.judge_id and config.judge_id != DEFAULT_USER_ID:
            judge = friend_map.get(str(config.judge_id))
            if judge:
                current_turn += 1
                await self._update_state(
                    db,
                    runtime,
                    run,
                    status="running",
                    phase="judge",
                    current_round=run.current_round,
                    current_turn=current_turn,
                    next_speaker_id=str(config.judge_id),
                    pause_reason=None,
                )
                host_message = self._build_host_message(
                    "debate",
                    "judge",
                    run.current_round,
                    judge.name,
                    topic,
                    None,
                )
                await self._dispatch_speaker(
                    db,
                    runtime,
                    run,
                    judge,
                    host_message,
                    str(config.judge_id),
                    "(empty)",
                    debate_side=None,
                )

        await self._end_run(db, runtime, run)

    async def _dispatch_speaker(
        self,
        db: Session,
        runtime: AutoDriveRuntime,
        run: GroupAutoDriveRun,
        friend: Friend,
        host_message: str,
        speaker_id: str,
        other_members_text: str,
        debate_side: Optional[str],
    ) -> None:
        user_msg = group_chat_shared.create_user_message(
            db=db,
            group_id=run.group_id,
            session_id=run.session_id,
            sender_id=DEFAULT_USER_ID,
            content=host_message,
            message_type="text",
            mentions=[speaker_id],
        )
        session = db.query(GroupSession).filter(GroupSession.id == run.session_id).first()
        if session:
            group_chat_shared.touch_session(db, session)

        ai_msg = group_chat_shared.create_ai_placeholder(
            db=db,
            group_id=run.group_id,
            session_id=run.session_id,
            friend_id=int(speaker_id),
            message_type="text",
            debate_side=debate_side,
        )

        llm_cfg = llm_service.get_active_config(db)
        model_name = llm_cfg.model_name if llm_cfg else "unknown"
        await runtime.queue.put({
            "event": "start",
            "data": {
                "message_id": user_msg.id,
                "group_id": run.group_id,
                "session_id": run.session_id,
                "model": model_name,
            },
        })

        await self._run_single_generation(
            db,
            runtime,
            run,
            friend,
            host_message,
            user_msg.id,
            ai_msg.id,
            other_members_text,
        )

    async def _run_single_generation(
        self,
        db: Session,
        runtime: AutoDriveRuntime,
        run: GroupAutoDriveRun,
        friend: Friend,
        message_content: str,
        user_msg_id: int,
        ai_msg_id: int,
        current_other_members: str,
    ) -> None:
        llm_config = llm_service.get_active_config(db)
        if not llm_config:
            await runtime.queue.put({"event": "auto_drive_error", "data": {"detail": "LLM Config missing"}})
            return

        raw_model_name = llm_config.model_name
        model_name = llm_service.normalize_model_name(raw_model_name)

        history_msgs = group_chat_shared.fetch_group_history(
            db=db,
            group_id=run.group_id,
            session_id=run.session_id,
            before_id=user_msg_id,
            limit=None,
        )

        name_map = group_chat_shared.build_name_map(
            db=db,
            messages=history_msgs,
            default_user_name="我",
            default_user_id=DEFAULT_USER_ID,
        )

        beijing_tz = timezone(timedelta(hours=8))
        now_time = datetime.now(timezone.utc).astimezone(beijing_tz)
        weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        current_time = f"{now_time:%Y-%m-%d 约%H}点 {weekday_map[now_time.weekday()]}"

        persona_prompt = (friend.system_prompt or get_prompt("chat/default_system_prompt.txt")).strip()

        auto_drive_rule = self._build_auto_drive_rule(
            run.mode,
            run.phase or "rounds",
            max(run.current_round, 1),
        )

        host_script = ""
        try:
            host_script = get_prompt(f"auto_drive/host_script_{run.mode}.txt").strip()
        except Exception:
            pass

        best_practice = ""
        try:
            best_practice = get_prompt(f"auto_drive/user_best_practice_{run.mode}.txt").strip()
        except Exception:
            pass

        script_prompt = "\n\n".join([p for p in [auto_drive_rule, host_script, best_practice] if p])
        segment_prompts: List[str] = []
        for prompt_name in (
            "auto_drive/message_segment_auto_drive.txt",
            "auto_drive/group_auto_drive_message_segment_normal.txt",
        ):
            try:
                loaded = get_prompt(prompt_name).strip()
                if loaded:
                    segment_prompts.append(loaded)
            except Exception:
                continue
        segment_prompt = "\n\n".join(segment_prompts)

        try:
            root_template = get_prompt("chat/root_system_prompt.txt")
            final_instructions = group_chat_shared.build_system_prompt(
                root_template=root_template,
                persona_prompt=persona_prompt,
                script_prompt=script_prompt,
                profile_data="",
                segment_prompt=segment_prompt,
                current_time=current_time,
            )
        except Exception:
            final_instructions = f"{persona_prompt}\n\n{script_prompt}\n\n{current_time}"

        current_other_members = current_other_members or "(empty)"
        mention_result = "被提及，需要发言"

        @function_tool(name_override="get_other_members_messages", description_override="")
        async def tool_get_other_members_messages():
            return current_other_members

        @function_tool(name_override="is_mentioned", description_override="")
        async def tool_is_mentioned():
            return mention_result

        agent_messages = group_chat_shared.build_group_context(
            history_msgs=history_msgs,
            name_map=name_map,
            self_id=int(friend.id),
            current_user_msg=message_content,
            user_msg_id=user_msg_id,
            current_other_members=current_other_members,
            mention_result=mention_result,
            injected_recall_messages=None,
        )

        logger.info(
            "[AutoDrive] AI Context for %s (ID: %s):\n%s",
            friend.name,
            friend.id,
            json.dumps(agent_messages, ensure_ascii=False, indent=2),
        )

        set_agents_default_client(llm_config, use_for_tracing=True)

        enable_thinking = runtime.enable_thinking
        if llm_config and enable_thinking and not llm_config.capability_reasoning:
            force_thinking = provider_rules.is_gemini_model(llm_config, llm_config.model_name)
            if not force_thinking:
                enable_thinking = False

        temperature = friend.temperature if friend.temperature is not None else 1.0
        top_p = friend.top_p if friend.top_p is not None else 0.9

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

        use_litellm = provider_rules.should_use_litellm(llm_config, raw_model_name)
        if use_litellm:
            from agents.extensions.models.litellm_model import LitellmModel
            gemini_model_name = provider_rules.normalize_gemini_model_name(raw_model_name)
            gemini_base_url = provider_rules.normalize_gemini_base_url(llm_config.base_url)
            agent_model = LitellmModel(model=gemini_model_name, base_url=gemini_base_url, api_key=llm_config.api_key)
        else:
            agent_model = model_name

        agent = Agent(
            name=friend.name,
            instructions=final_instructions,
            model=agent_model,
            model_settings=model_settings,
            tools=group_chat_shared.build_agent_tools(
                tool_get_other_members_messages,
                tool_is_mentioned,
            ),
        )

        await group_chat_shared.stream_llm_to_queue(
            agent=agent,
            agent_messages=agent_messages,
            queue=runtime.queue,
            enable_thinking=enable_thinking,
            sender_id=friend.id,
            message_id=ai_msg_id,
            session_id=run.session_id,
            db=db,
            sanitize_message_tags=bool(friend.enable_voice),
        )

        if friend.enable_voice:
            try:
                final_msg = db.query(GroupMessage).filter(GroupMessage.id == ai_msg_id).first()
                final_content = (final_msg.content or "") if final_msg else ""

                async def _on_voice_segment_ready(segment_data: Dict[str, object]):
                    await runtime.queue.put({
                        "event": "voice_segment",
                        "data": {
                            "sender_id": str(friend.id),
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
                    on_segment_ready=_on_voice_segment_ready,
                )
                if voice_payload and final_msg:
                    final_msg.voice_payload = voice_payload
                    db.commit()
                    await runtime.queue.put({
                        "event": "voice_payload",
                        "data": {
                            "sender_id": str(friend.id),
                            "message_id": ai_msg_id,
                            "voice_payload": voice_payload,
                        },
                    })
            except Exception as voice_exc:
                logger.warning("[AutoDrive] Voice synthesis failed for message=%s: %s", ai_msg_id, voice_exc)

    async def _update_state(
        self,
        db: Session,
        runtime: AutoDriveRuntime,
        run: GroupAutoDriveRun,
        status: str,
        phase: str,
        current_round: int,
        current_turn: int,
        next_speaker_id: Optional[str],
        pause_reason: Optional[str],
    ) -> None:
        run.status = status
        run.phase = phase
        run.current_round = current_round
        run.current_turn = current_turn
        run.next_speaker_id = next_speaker_id
        run.pause_reason = pause_reason
        run.update_time = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})

    async def _wait_if_paused(self, db: Session, runtime: AutoDriveRuntime, run: GroupAutoDriveRun) -> bool:
        if runtime.stop_event.is_set():
            return False

        if runtime.pause_requested:
            run.status = "paused"
            run.pause_reason = "等待收尾"
            run.update_time = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})
            runtime.pause_event.clear()
            runtime.pause_requested = False

        await runtime.pause_event.wait()
        return not runtime.stop_event.is_set()

    async def _end_run(self, db: Session, runtime: AutoDriveRuntime, run: GroupAutoDriveRun) -> None:
        run.status = "ended"
        run.ended_at = datetime.now(timezone.utc)
        run.update_time = run.ended_at
        run.next_speaker_id = None
        db.commit()
        db.refresh(run)

        await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})
        await runtime.queue.put({"event": "auto_drive_done", "data": {"run_id": run.id}})

    async def _finalize_runtime(self, run_id: int) -> None:
        runtime = None
        for group_id, r in list(self._runtimes.items()):
            if r.run_id == run_id:
                runtime = r
                self._runtimes.pop(group_id, None)
                break
        if runtime:
            await runtime.queue.put(None)

    async def _ensure_run_closed(self, run_id: int) -> None:
        try:
            with SessionLocal() as db:
                run = db.query(GroupAutoDriveRun).filter(GroupAutoDriveRun.id == run_id).first()
                if not run or run.status == "ended":
                    return
                now_time = datetime.now(timezone.utc)
                run.status = "ended"
                run.ended_at = now_time
                run.update_time = now_time
                run.next_speaker_id = None
                db.commit()

                runtime = self._runtimes.get(run.group_id)
                if runtime:
                    await runtime.queue.put({"event": "auto_drive_state", "data": self._state_payload(run)})
                    await runtime.queue.put({"event": "auto_drive_done", "data": {"run_id": run.id}})
        except Exception as e:
            logger.warning(f"[AutoDrive] ensure_run_closed failed: {e}")


group_auto_drive_service = GroupAutoDriveService()
