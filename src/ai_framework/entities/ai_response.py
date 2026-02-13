from __future__ import annotations

from pydantic import BaseModel

from ai_framework.entities.token_usage import TokenUsage
from ai_framework.entities.tool import ToolCall


class AIResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []
    stop_reason: str | None = None
    usage: TokenUsage | None = None
