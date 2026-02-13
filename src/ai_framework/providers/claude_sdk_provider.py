import asyncio
from typing import Any, Literal

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.token_usage import TokenUsage
from ai_framework.entities.tool import ToolCall
from ai_framework.protocols.tool_definition import ToolDefinition

type PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]


class ClaudeSdkProvider:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        cwd: str | None = None,
        permission_mode: PermissionMode = "default",
    ) -> None:
        self._model = model
        self._cwd = cwd
        self._permission_mode: PermissionMode = permission_mode
        self._last_session_id: str | None = None

    @property
    def last_session_id(self) -> str | None:
        return self._last_session_id

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        return asyncio.run(self._send_message_async(messages, system, tools))

    async def _send_message_async(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
    ) -> AIResponse:
        prompt = self._build_prompt(messages)

        options = ClaudeCodeOptions(
            model=self._model,
            permission_mode=self._permission_mode,
            resume=self._last_session_id,
        )

        if self._cwd:
            options.cwd = self._cwd

        if system:
            options.system_prompt = system

        if tools:
            options.allowed_tools = [t.name for t in tools]

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        usage: TokenUsage | None = None

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                name=block.name,
                                arguments=self._normalize_arguments(block.input),
                            )
                        )
            elif isinstance(msg, ResultMessage):
                self._last_session_id = msg.session_id
                usage = self._extract_usage(msg)

        return AIResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason="end_turn",
            usage=usage,
        )

    def _build_prompt(self, messages: list[Message]) -> str:
        # claude-code-sdk query() accepts a single prompt string, not a messages list.
        # When resuming a session, the SDK retains prior conversation context,
        # so only the latest user message is needed.
        # On a fresh session, we concatenate the full history to avoid context loss.
        if self._last_session_id:
            for msg in reversed(messages):
                if msg.role == "user":
                    return msg.content
            return ""

        parts: list[str] = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            parts.append(f"[{prefix}]: {msg.content}")
        return "\n\n".join(parts)

    def _normalize_arguments(
        self, raw_input: dict[str, Any]
    ) -> dict[str, object]:
        return dict(raw_input)

    def _extract_usage(self, result: ResultMessage) -> TokenUsage:
        raw_usage = result.usage or {}
        input_tokens = (
            raw_usage.get("input_tokens", 0)
            + raw_usage.get("cache_creation_input_tokens", 0)
            + raw_usage.get("cache_read_input_tokens", 0)
        )
        output_tokens = raw_usage.get("output_tokens", 0)
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
