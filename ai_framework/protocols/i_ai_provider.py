from __future__ import annotations

from typing import Any, Protocol

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.protocols.base_tool import BaseTool


class IAIProvider(Protocol):
    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[BaseTool] | None = None,
        tool_context: dict[str, Any] | None = None,
        # Тред разговора. Провайдеру без состояния он не нужен, но провайдер, который
        # держит сессию на стороне модели, обязан знать, ЧЕЙ разговор продолжает:
        # одна сессия на провайдер склеивает разных собеседников (ClaudeSdkProvider).
        thread_id: str | None = None,
    ) -> AIResponse: ...
