from __future__ import annotations

from typing import Protocol

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.protocols.tool_definition import ToolDefinition


class IAIProvider(Protocol):
    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse: ...
