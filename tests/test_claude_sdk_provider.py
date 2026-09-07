from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, ClassVar

import pytest

pytest.importorskip("claude_agent_sdk")

from pydantic import BaseModel

from ai_framework.entities.message import Message
from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool
from ai_framework.providers.claude_sdk_provider import (
    ClaudeSdkProvider,
    _thread_key,
)


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


def test_build_prompt_on_resume_keeps_notes_added_after_last_answer():
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="привет"),
        Message(role="assistant", content="здравствуйте"),
        Message(role="user", content="[SYSTEM NOTE] бот отправил карточку устройства"),
        Message(role="user", content="а что с ним?"),
    ]

    prompt = provider._build_prompt(messages, resumed=True)

    assert prompt == (
        "[SYSTEM NOTE] бот отправил карточку устройства\n\nа что с ним?"
    )


def test_build_prompt_on_resume_keeps_single_user_message():
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="привет"),
        Message(role="assistant", content="здравствуйте"),
        Message(role="user", content="а что с ним?"),
    ]

    assert provider._build_prompt(messages, resumed=True) == "а что с ним?"


def test_build_prompt_without_session_keeps_full_history():
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="привет"),
        Message(role="assistant", content="здравствуйте"),
    ]

    assert provider._build_prompt(messages) == (
        "[User]: привет\n\n[Assistant]: здравствуйте"
    )


def test_session_is_kept_per_thread():
    provider = ClaudeSdkProvider()

    provider._session_ids[_thread_key("chat-a")] = "session-a"

    assert provider.session_id_of("chat-a") == "session-a"
    assert provider.session_id_of("chat-b") is None


def test_answer_to_one_thread_does_not_resume_another():
    """Тот самый прод-случай: два чата подряд, второй не должен попасть в сессию первого."""
    provider = ClaudeSdkProvider()

    provider._session_ids[_thread_key("chat-a")] = "session-a"
    provider._session_ids[_thread_key("chat-b")] = "session-b"

    assert provider.session_id_of("chat-a") == "session-a"
    assert provider.session_id_of("chat-b") == "session-b"


def test_thread_omitted_keeps_single_session():
    provider = ClaudeSdkProvider()

    provider._session_ids[_thread_key(None)] = "session-default"

    assert provider.last_session_id == "session-default"
    assert provider.session_id_of() == "session-default"
    assert provider.session_id_of("") == "session-default"
    assert provider.session_id_of("chat-a") is None


def _result_message(session_id: str) -> Any:
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id=session_id,
    )


def _capturing_query(
    seen: list[str | None], session_ids: list[str]
) -> Callable[..., AsyncIterator[Any]]:
    """Подменяет `query`: запоминает, с каким `resume` позвали, и отдаёт свою сессию."""
    handed = iter(session_ids)

    async def _fake(prompt: str, options: Any) -> AsyncIterator[Any]:  # noqa: ANN401, ARG001
        seen.append(options.resume)
        yield _result_message(next(handed))

    return _fake


def test_resume_follows_the_thread_not_the_last_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Прод-случай 07.09.2026: ответ одному чату уезжал в сессию другого."""
    provider = ClaudeSdkProvider()
    seen: list[str | None] = []
    monkeypatch.setattr(
        "ai_framework.providers.claude_sdk_provider.query",
        _capturing_query(seen, ["session-a", "session-b", "session-a2"]),
    )

    provider.send_message([Message(role="user", content="первый")], thread_id="chat-a")
    provider.send_message([Message(role="user", content="второй")], thread_id="chat-b")
    provider.send_message(
        [Message(role="user", content="снова первый")], thread_id="chat-a"
    )

    # Третий вызов — снова чат A, и продолжает он СВОЮ сессию, а не последнюю по времени.
    assert seen == [None, None, "session-a"]
    assert provider.session_id_of("chat-a") == "session-a2"
    assert provider.session_id_of("chat-b") == "session-b"


def test_resume_without_thread_keeps_previous_behaviour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ClaudeSdkProvider()
    seen: list[str | None] = []
    monkeypatch.setattr(
        "ai_framework.providers.claude_sdk_provider.query",
        _capturing_query(seen, ["session-1", "session-1"]),
    )

    provider.send_message([Message(role="user", content="раз")])
    provider.send_message([Message(role="user", content="два")])

    assert seen == [None, "session-1"]
    assert provider.last_session_id == "session-1"
