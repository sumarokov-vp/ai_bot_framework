from __future__ import annotations

import asyncio
import json
from typing import Any, ClassVar

import pytest

pytest.importorskip("claude_agent_sdk")

from pydantic import BaseModel

from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool
from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider


class _EchoInput(BaseModel):
    text: str


class _EchoTool(BaseTool):
    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "Echoes provided text"
    Input: ClassVar[type[BaseModel]] = _EchoInput

    def execute(self, input: _EchoInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        return {"echo": input.text, "user_id": context.get("user_id")}


class _FailingTool(BaseTool):
    name: ClassVar[str] = "boom"
    description: ClassVar[str] = "Always fails"
    Input: ClassVar[type[BaseModel]] = _EchoInput

    def execute(self, input: _EchoInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        raise RuntimeError("kaboom")


class _SuppressTool(BaseTool):
    name: ClassVar[str] = "silent"
    description: ClassVar[str] = "Suppresses LLM response"
    suppress_response: ClassVar[bool] = True
    Input: ClassVar[type[BaseModel]] = _EchoInput

    def execute(self, input: _EchoInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        return "ok"


def _invoke_wrapper(
    provider: ClaudeSdkProvider,
    wrapper: Any,
    args: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handler = getattr(wrapper, "handler", wrapper)

    async def _runner() -> dict[str, Any]:
        provider._context_var.set(context or {})
        provider._suppress_response_flag_var.set(False)
        return await handler(args)

    return asyncio.run(_runner())


def test_build_mcp_server_registers_tool_names():
    provider = ClaudeSdkProvider()
    tools: list[BaseTool] = [_EchoTool()]

    provider._build_mcp_server(tools)

    assert provider._mcp_server is not None
    assert provider._registered_tool_names == {"echo"}


def test_wrap_tool_returns_text_content_for_success():
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_EchoTool())

    result = _invoke_wrapper(provider, wrapper, {"text": "hi"}, {"user_id": 42})

    assert result["content"][0]["type"] == "text"
    payload = json.loads(result["content"][0]["text"])
    assert payload == {"echo": "hi", "user_id": 42}
    assert "isError" not in result


def test_wrap_tool_returns_is_error_on_exception():
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_FailingTool())

    result = _invoke_wrapper(provider, wrapper, {"text": "hi"})

    assert result["isError"] is True
    assert "kaboom" in result["content"][0]["text"]


def test_wrap_tool_sets_suppress_response_flag():
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_SuppressTool())
    handler = getattr(wrapper, "handler", wrapper)

    async def _runner() -> bool:
        provider._context_var.set({})
        provider._suppress_response_flag_var.set(False)
        await handler({"text": "hi"})
        return provider._suppress_response_flag_var.get()

    assert asyncio.run(_runner()) is True


def test_wrap_tool_does_not_set_suppress_flag_for_regular_tool():
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_EchoTool())
    handler = getattr(wrapper, "handler", wrapper)

    async def _runner() -> bool:
        provider._context_var.set({})
        provider._suppress_response_flag_var.set(False)
        await handler({"text": "hi"})
        return provider._suppress_response_flag_var.get()

    assert asyncio.run(_runner()) is False
