from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest

pytest.importorskip("claude_agent_sdk")

from pydantic import BaseModel

from ai_framework.entities.attachment import Attachment
from ai_framework.entities.message import Message
from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool
from ai_framework.providers import claude_sdk_provider
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
        provider._suppressing_tools_var.set(set())
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
        suppressing_tools: set[str] = set()
        provider._context_var.set({})
        provider._suppressing_tools_var.set(suppressing_tools)
        await handler({"text": "hi"})
        return bool(suppressing_tools)

    assert asyncio.run(_runner()) is True


def test_wrap_tool_does_not_set_suppress_flag_for_regular_tool():
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_EchoTool())
    handler = getattr(wrapper, "handler", wrapper)

    async def _runner() -> bool:
        suppressing_tools: set[str] = set()
        provider._context_var.set({})
        provider._suppressing_tools_var.set(suppressing_tools)
        await handler({"text": "hi"})
        return bool(suppressing_tools)

    assert asyncio.run(_runner()) is False


def test_build_prompt_on_resume_keeps_notes_added_after_last_answer():
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="привет"),
        Message(role="assistant", content="здравствуйте"),
        Message(role="user", content="[SYSTEM NOTE] бот отправил карточку устройства"),
        Message(role="user", content="а что с ним?"),
    ]

    prompt = provider._build_prompt(messages, "session-1")

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

    assert provider._build_prompt(messages, "session-1") == "а что с ним?"


def test_build_prompt_without_session_keeps_full_history():
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="привет"),
        Message(role="assistant", content="здравствуйте"),
    ]

    assert provider._build_prompt(messages, None) == (
        "[User]: привет\n\n[Assistant]: здравствуйте"
    )


_PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"
_PDF_BYTES = b"%PDF-1.7 fake-pdf"


def _png(data: bytes = _PNG_BYTES) -> Attachment:
    return Attachment(media_type="image/png", data=data, key="k1.png")


def _pdf(data: bytes = _PDF_BYTES) -> Attachment:
    return Attachment(media_type="application/pdf", data=data, key="k2.pdf")


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


class _QueryRecorder:
    def __init__(self) -> None:
        self.prompt: str | None = None
        self.streamed: list[dict[str, Any]] | None = None

    def __call__(self, *, prompt: Any, options: Any) -> AsyncIterator[Any]:
        return self._run(prompt)

    async def _run(self, prompt: Any) -> AsyncIterator[Any]:
        if isinstance(prompt, str):
            self.prompt = prompt
        else:
            self.streamed = [message async for message in prompt]
        return
        yield


@pytest.fixture
def recorded_query(monkeypatch: pytest.MonkeyPatch) -> _QueryRecorder:
    recorder = _QueryRecorder()
    monkeypatch.setattr(claude_sdk_provider, "query", recorder)
    return recorder


def _single_streamed_content(recorder: _QueryRecorder) -> list[dict[str, Any]]:
    assert recorder.prompt is None
    assert recorder.streamed is not None
    assert len(recorder.streamed) == 1
    streamed = recorder.streamed[0]
    assert streamed["type"] == "user"
    assert streamed["parent_tool_use_id"] is None
    assert streamed["message"]["role"] == "user"
    return streamed["message"]["content"]


def test_send_message_without_session_streams_attachments_of_whole_history(
    recorded_query: _QueryRecorder,
):
    provider = ClaudeSdkProvider()
    messages = [
        Message(role="user", content="вот паспорт", attachments=[_png()]),
        Message(role="assistant", content="вижу"),
        Message(role="user", content="и договор", attachments=[_pdf()]),
    ]

    provider.send_message(messages)

    content = _single_streamed_content(recorded_query)
    assert content == [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": _b64(_PNG_BYTES),
            },
        },
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": _b64(_PDF_BYTES),
            },
        },
        {
            "type": "text",
            "text": "[User]: вот паспорт\n\n[Assistant]: вижу\n\n[User]: и договор",
        },
    ]


def test_send_message_on_resume_streams_only_tail_attachments(
    recorded_query: _QueryRecorder,
):
    provider = ClaudeSdkProvider()
    provider._thread_sessions[None] = "session-1"
    messages = [
        Message(role="user", content="вот паспорт", attachments=[_png(b"old")]),
        Message(role="assistant", content="вижу"),
        Message(role="user", content="[SYSTEM NOTE] прислан файл"),
        Message(role="user", content="что в договоре?", attachments=[_pdf()]),
    ]

    provider.send_message(messages)

    content = _single_streamed_content(recorded_query)
    assert [block["type"] for block in content] == ["document", "text"]
    assert content[0]["source"]["data"] == _b64(_PDF_BYTES)
    assert content[1] == {
        "type": "text",
        "text": "[SYSTEM NOTE] прислан файл\n\nчто в договоре?",
    }


def test_send_message_without_attachments_passes_string_prompt(
    recorded_query: _QueryRecorder,
):
    provider = ClaudeSdkProvider()
    provider._thread_sessions[None] = "session-1"
    messages = [
        Message(role="user", content="вот паспорт", attachments=[_png()]),
        Message(role="assistant", content="вижу"),
        Message(role="user", content="спасибо"),
    ]

    provider.send_message(messages)

    assert recorded_query.streamed is None
    assert recorded_query.prompt == "спасибо"


def test_build_prompt_with_attachment_only_message_omits_empty_text():
    provider = ClaudeSdkProvider()
    messages = [Message(role="user", content="", attachments=[_png()])]

    prompt = provider._build_prompt(messages, "session-1")

    assert not isinstance(prompt, str)

    async def _collect() -> list[dict[str, Any]]:
        return [message async for message in prompt]

    streamed = asyncio.run(_collect())
    assert [block["type"] for block in streamed[0]["message"]["content"]] == [
        "image"
    ]


def test_build_prompt_rejects_attachment_without_data_before_query():
    provider = ClaudeSdkProvider()
    messages = [
        Message(
            role="user",
            content="вот",
            attachments=[Attachment(media_type="image/png", key="k1.png")],
        )
    ]

    with pytest.raises(ValueError, match="k1.png"):
        provider._build_prompt(messages, None)
