from __future__ import annotations

import asyncio
import contextvars
import json
import logging
from typing import Any, Literal

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool as mcp_tool,
)
from claude_agent_sdk.types import McpSdkServerConfig

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.token_usage import TokenUsage
from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool

logger = logging.getLogger(__name__)

type PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]



# Тред, под которым живёт сессия у того, кто зовёт провайдера без `thread_id`. Пустая
# строка, а не `None`: ключ словаря обязан быть строкой, а «безымянный разговор» — это
# один разговор, а не отсутствие разговора.
_DEFAULT_THREAD = ""


def _thread_key(thread_id: str | None) -> str:
    return thread_id if thread_id else _DEFAULT_THREAD


class ClaudeSdkProvider:
    """Провайдер поверх Claude Code CLI. Сессия CLI — СВОЯ НА КАЖДЫЙ ТРЕД.

    Провайдер у приложения один на процесс, а разговоров в нём столько, сколько чатов.
    Пока `resume` брался из одного поля на весь провайдер, он указывал на сессию того,
    кто ответил последним: реплика одного собеседника продолжала разговор другого, и
    чужая переписка приезжала в контекст модели. Поэтому ключ здесь — тред, а не порядок
    обращений.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        cwd: str | None = None,
        permission_mode: PermissionMode = "default",
        mcp_server_name: str = "ai-framework-tools",
    ) -> None:
        self._model = model
        self._cwd = cwd
        self._permission_mode: PermissionMode = permission_mode
        self._mcp_server_name = mcp_server_name
        self._session_ids: dict[str, str] = {}
        self._mcp_server: McpSdkServerConfig | None = None
        self._registered_tool_names: set[str] = set()
        self._context_var: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar("ai_framework_tool_context", default=None)
        )
        self._suppress_response_flag_var: contextvars.ContextVar[bool] = (
            contextvars.ContextVar(
                "ai_framework_suppress_response_flag", default=False
            )
        )

    @property
    def last_session_id(self) -> str | None:
        """Сессия треда по умолчанию — того, кого зовут без `thread_id`."""
        return self._session_ids.get(_DEFAULT_THREAD)

    def session_id_of(self, thread_id: str | None = None) -> str | None:
        """Сессия CLI, в которую уйдёт `resume` для этого треда."""
        return self._session_ids.get(_thread_key(thread_id))

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[BaseTool] | None = None,
        tool_context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AIResponse:
        return asyncio.run(
            self._send_message_async(
                messages, system, tools, tool_context, thread_id
            )
        )

    async def _send_message_async(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[BaseTool] | None = None,
        tool_context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AIResponse:
        thread = _thread_key(thread_id)
        resume = self._session_ids.get(thread)
        if tools:
            tool_names = {t.name for t in tools}
            if self._mcp_server is None or tool_names != self._registered_tool_names:
                self._build_mcp_server(tools)

        self._context_var.set(tool_context or {})
        self._suppress_response_flag_var.set(False)

        options = ClaudeAgentOptions(
            model=self._model,
            permission_mode=self._permission_mode,
            resume=resume,
        )

        if self._cwd:
            options.cwd = self._cwd

        if system:
            options.system_prompt = system

        if tools and self._mcp_server is not None:
            options.mcp_servers = {self._mcp_server_name: self._mcp_server}
            options.allowed_tools = [
                f"mcp__{self._mcp_server_name}__{t.name}" for t in tools
            ]

        prompt = self._build_prompt(messages, resumed=resume is not None)

        text_parts: list[str] = []
        usage: TokenUsage | None = None

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        logger.debug(
                            "SDK tool use: %s(%s)", block.name, block.input
                        )
                    elif isinstance(block, ToolResultBlock):
                        logger.debug(
                            "SDK tool result: %s -> %s",
                            block.tool_use_id,
                            block.content,
                        )
            elif isinstance(msg, ResultMessage):
                self._session_ids[thread] = msg.session_id
                usage = self._extract_usage(msg)

        return AIResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=[],
            stop_reason="end_turn",
            usage=usage,
            suppress_response=self._suppress_response_flag_var.get(),
        )

    def _build_mcp_server(self, tools: list[BaseTool]) -> None:
        wrapped = [self._wrap_tool(t) for t in tools]
        self._mcp_server = create_sdk_mcp_server(
            name=self._mcp_server_name,
            version="1.0.0",
            tools=wrapped,
        )
        self._registered_tool_names = {t.name for t in tools}

    def _wrap_tool(self, base_tool: BaseTool) -> Any:
        context_var = self._context_var
        suppress_flag_var = self._suppress_response_flag_var

        @mcp_tool(base_tool.name, base_tool.description, base_tool.input_schema)
        async def _wrapper(args: dict[str, Any]) -> dict[str, Any]:
            input_obj = base_tool.Input(**args)
            ctx_data = context_var.get() or {}
            ctx = ToolContext(ctx_data)
            try:
                result = base_tool.execute(input_obj, ctx)
            except Exception as exc:
                logger.exception("Tool %s failed", base_tool.name)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Tool {base_tool.name} failed: {exc}",
                        }
                    ],
                    "isError": True,
                }
            if getattr(base_tool, "suppress_response", False):
                suppress_flag_var.set(True)
            text = (
                result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=False, default=str)
            )
            return {"content": [{"type": "text", "text": text}]}

        return _wrapper

    def _build_prompt(
        self, messages: list[Message], resumed: bool = False
    ) -> str:
        if resumed:
            tail: list[str] = []
            for msg in reversed(messages):
                if msg.role == "assistant":
                    break
                if msg.role == "user":
                    tail.append(msg.content)
            return "\n\n".join(reversed(tail))

        parts: list[str] = []
        for msg in messages:
            prefix = "User" if msg.role == "user" else "Assistant"
            parts.append(f"[{prefix}]: {msg.content}")
        return "\n\n".join(parts)

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
