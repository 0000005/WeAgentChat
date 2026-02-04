from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field, model_validator


AutoDriveMode = Literal["brainstorm", "decision", "debate"]
AutoDriveEndAction = Literal["summary", "judge", "both"]


class AutoDriveConfig(BaseModel):
    mode: AutoDriveMode
    topic: Dict[str, Any]
    roles: Dict[str, Any]
    turn_limit: int = Field(..., ge=1)
    end_action: AutoDriveEndAction
    judge_id: Optional[str] = None
    summary_by: Optional[str] = None

    @model_validator(mode="after")
    def validate_config(self):
        topic = self.topic or {}
        roles = self.roles or {}

        def _pick_topic(*keys: str) -> Optional[str]:
            for key in keys:
                value = topic.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return None

        def _pick_list(*keys: str) -> List[str]:
            for key in keys:
                value = roles.get(key)
                if isinstance(value, list):
                    return [str(v) for v in value if str(v).strip()]
            return []

        if self.mode == "brainstorm":
            if not _pick_topic("theme", "主题", "topic"):
                raise ValueError("brainstorm 需要主题字段")
            if not _pick_topic("goal", "目标"):
                raise ValueError("brainstorm 需要目标字段")
            if not _pick_topic("constraints", "约束"):
                raise ValueError("brainstorm 需要约束字段")

            participants = _pick_list("participants", "参与成员")
            if not participants:
                raise ValueError("brainstorm 需要参与成员列表")

        if self.mode == "decision":
            if not _pick_topic("question", "决策问题"):
                raise ValueError("decision 需要决策问题字段")
            if not _pick_topic("criteria", "评估标准"):
                raise ValueError("decision 需要评估标准字段")
            options = topic.get("options") or topic.get("候选方案") or topic.get("candidate_options")
            if not options:
                raise ValueError("decision 需要候选方案字段")

            participants = _pick_list("participants", "参与成员")
            if not participants:
                raise ValueError("decision 需要参与成员列表")

        if self.mode == "debate":
            if not _pick_topic("motion", "辩题"):
                raise ValueError("debate 需要辩题字段")
            if not _pick_topic("affirmative", "正方立场"):
                raise ValueError("debate 需要正方立场字段")
            if not _pick_topic("negative", "反方立场"):
                raise ValueError("debate 需要反方立场字段")

            affirmative = _pick_list("affirmative", "正方")
            negative = _pick_list("negative", "反方")
            if not affirmative or not negative:
                raise ValueError("debate 需要正反方成员列表")
            if len(affirmative) > 2 or len(negative) > 2:
                raise ValueError("debate 正反方最多 2 人")
            if len(affirmative) != len(negative):
                raise ValueError("debate 正反人数必须相等")
            if self.end_action in ("judge", "both"):
                if not self.judge_id:
                    raise ValueError("debate 需要评委成员")
                if self.judge_id in affirmative or self.judge_id in negative:
                    raise ValueError("评委不能是辩论选手")

        return self


class AutoDriveStartRequest(BaseModel):
    group_id: int
    config: AutoDriveConfig
    enable_thinking: bool = False


class AutoDriveActionRequest(BaseModel):
    group_id: int


class AutoDriveStateRead(BaseModel):
    run_id: int
    group_id: int
    session_id: int
    mode: AutoDriveMode
    status: str
    phase: Optional[str] = None
    current_round: int
    current_turn: int
    next_speaker_id: Optional[str] = None
    pause_reason: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    topic: Dict[str, Any]
    roles: Dict[str, Any]
    turn_limit: int
    end_action: AutoDriveEndAction
    judge_id: Optional[str] = None
    summary_by: Optional[str] = None

    class Config:
        from_attributes = True
