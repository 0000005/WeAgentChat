"""
SSE 响应事件 Schema 定义
用于 chat.py 中的 send_message_stream 函数
"""
from typing import Literal, Optional, TypedDict
from datetime import datetime


class StartEventData(TypedDict):
    """会话开始事件数据"""
    session_id: int
    message_id: Optional[int]  # AI 消息 ID，流开始时可能还未分配
    user_message_id: int
    model: str
    persona_id: int
    persona_name: str
    created_at: str  # ISO 8601 格式


class ThinkingEventData(TypedDict):
    """思考过程事件数据"""
    delta: str  # 思考内容片段


class MessageEventData(TypedDict):
    """普通回复事件数据"""
    delta: str  # 回复内容片段


class ToolCallEventData(TypedDict):
    """工具调用事件数据"""
    stage: Literal["start", "delta", "complete"]
    call_id: str
    name: Optional[str]  # stage=start/complete 时必填
    arguments: Optional[str]  # stage=complete 时的完整参数 JSON 字符串
    args_delta: Optional[str]  # stage=delta 时的增量参数片段


class ToolResultEventData(TypedDict):
    """工具执行结果事件数据"""
    call_id: str
    result: str  # 工具执行结果（可以是 JSON 字符串）


class ErrorEventData(TypedDict):
    """错误事件数据"""
    code: str  # 错误代码，如 "llm_error", "context_length_exceeded"
    detail: str  # 错误详细信息


class UsageInfo(TypedDict):
    """Token 使用统计"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class DoneEventData(TypedDict):
    """流结束事件数据"""
    finish_reason: Literal["stop", "length", "tool_calls", "error"]
    usage: Optional[UsageInfo]


# SSE 事件类型枚举
SSEEventType = Literal["start", "thinking", "message", "tool_call", "tool_result", "error", "done"]
