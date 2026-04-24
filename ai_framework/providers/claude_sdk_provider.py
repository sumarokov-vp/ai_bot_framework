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


class ClaudeSdkProvider:
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
        self._last_session_id: str | None = None
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
        return self._last_session_id

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[BaseTool] | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> AIResponse:
        return asyncio.run(
            self._send_message_async(messages, system, tools, tool_context)
        )

    async def _send_message_async(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: list[BaseTool] | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> AIResponse:
        if tools:
            tool_names = {t.name for t in tools}
            if self._mcp_server is None or tool_names != self._registered_tool_names:
                self._build_mcp_server(tools)

        self._context_var.set(tool_context or {})
        self._suppress_response_flag_var.set(False)

        options = ClaudeAgentOptions(
            model=self._model,
            permission_mode=self._permission_mode,
            resume=self._last_session_id,
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

        prompt = self._build_prompt(messages)

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
                self._last_session_id = msg.session_id
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

    def _build_prompt(self, messages: list[Message]) -> str:
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
