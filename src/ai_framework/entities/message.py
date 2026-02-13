from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ai_framework.entities.tool import ToolCall, ToolResult


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_results: list[ToolResult] | None = None
