from __future__ import annotations

from typing import Optional

try:
    from openai.types.responses import (
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseReasoningSummaryTextDeltaEvent,
        ResponseReasoningTextDeltaEvent,
    )
except Exception:  # pragma: no cover - fallback for older SDKs
    ResponseContentPartAddedEvent = None
    ResponseContentPartDoneEvent = None
    ResponseReasoningSummaryTextDeltaEvent = None
    ResponseReasoningTextDeltaEvent = None


def extract_reasoning_delta(event_data: object) -> Optional[str]:
    if event_data is None:
        return None

    if ResponseReasoningTextDeltaEvent and isinstance(event_data, ResponseReasoningTextDeltaEvent):
        return event_data.delta or ""

    if ResponseReasoningSummaryTextDeltaEvent and isinstance(
        event_data, ResponseReasoningSummaryTextDeltaEvent
    ):
        return event_data.delta or ""

    if ResponseContentPartAddedEvent and isinstance(event_data, ResponseContentPartAddedEvent):
        part = getattr(event_data, "part", None)
        if getattr(part, "type", None) == "reasoning_text":
            return getattr(part, "text", None) or ""

    if ResponseContentPartDoneEvent and isinstance(event_data, ResponseContentPartDoneEvent):
        part = getattr(event_data, "part", None)
        if getattr(part, "type", None) == "reasoning_text":
            return getattr(part, "text", None) or ""

    return None
