from __future__ import annotations

import base64
import json

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from pydantic import BaseModel

from ai_framework.attachments.in_memory_attachment_store import InMemoryAttachmentStore
from ai_framework.entities.attachment import Attachment
from ai_framework.entities.tool import ToolResult
from ai_framework.entities.tool_context import ToolContext
from ai_framework.memory.in_memory_store import InMemoryStore
from ai_framework.protocols.base_tool import BaseTool, ToolOutput
from ai_framework.providers.anthropic_provider import AnthropicProvider
from ai_framework.session.in_memory_session_store import InMemorySessionStore
from ai_framework.tool_loop import ToolLoop
from ai_framework.tools.tool_registry import ToolRegistry


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-payload"
PNG_BASE64 = base64.standard_b64encode(PNG_BYTES).decode("ascii")
THREAD = "thread-1"


class _NoInput(BaseModel):
    pass


class _ReturningTool(BaseTool):
    name: ClassVar[str] = "show"
    description: ClassVar[str] = "Returns a prepared result"
    Input: ClassVar[type[BaseModel]] = _NoInput

    def __init__(self, result: ToolOutput) -> None:
        self._result = result

    def execute(self, input: _NoInput, context: ToolContext) -> ToolOutput:  # noqa: ANN001, A002
        return self._result


class _ScriptedMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        last = kwargs["messages"][-1]
        wants_tool = last["role"] == "user" and isinstance(last["content"], str)
        if wants_tool and len(self.calls) == 1:
            content = [SimpleNamespace(type="tool_use", id="call_1", name="show", input={})]
            stop_reason = "tool_use"
        else:
            content = [SimpleNamespace(type="text", text="готово")]
            stop_reason = "end_turn"
        return SimpleNamespace(
            content=content,
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


def _loop(
    monkeypatch: pytest.MonkeyPatch,
    result: ToolOutput,
    attachment_store: InMemoryAttachmentStore | None,
) -> tuple[ToolLoop, _ScriptedMessages, InMemoryStore]:
    provider = AnthropicProvider(api_key="test-key")
    scripted = _ScriptedMessages()
    monkeypatch.setattr(provider, "_client", SimpleNamespace(messages=scripted))
    registry = ToolRegistry()
    registry.register(_ReturningTool(result))
    memory = InMemoryStore()
    loop = ToolLoop(
        provider=provider,
        memory=memory,
        sessions=InMemorySessionStore(),
        tool_registry=registry,
        system_prompt="system",
        attachment_store=attachment_store,
    )
    return loop, scripted, memory


def _sent_tool_result(call: dict[str, Any]) -> dict[str, Any]:
    tool_message = call["messages"][2]
    assert tool_message["role"] == "user"
    return tool_message["content"][0]


def _stored_tool_result(memory: InMemoryStore) -> ToolResult:
    tool_message = memory.get_messages(THREAD)[2]
    assert tool_message.tool_results is not None
    return tool_message.tool_results[0]


def test_text_and_png_reach_claude_as_text_and_image_blocks(
    monkeypatch: pytest.MonkeyPatch,
):
    png = Attachment(media_type="image/png", filename="chart.png", data=PNG_BYTES)
    loop, scripted, _ = _loop(monkeypatch, ["Вот график", png], InMemoryAttachmentStore())

    loop.run(THREAD, "покажи график")

    tool_result = _sent_tool_result(scripted.calls[1])
    assert tool_result["tool_use_id"] == "call_1"
    assert tool_result["content"] == [
        {"type": "text", "text": "Вот график"},
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": PNG_BASE64},
        },
    ]


def test_history_keeps_attachment_key_without_bytes(monkeypatch: pytest.MonkeyPatch):
    store = InMemoryAttachmentStore()
    png = Attachment(media_type="image/png", data=PNG_BYTES)
    loop, _, memory = _loop(monkeypatch, ["Вот график", png], store)

    loop.run(THREAD, "покажи график")

    stored = _stored_tool_result(memory)
    assert stored.content == "Вот график"
    assert stored.attachments is not None
    key = stored.attachments[0].key
    assert key is not None
    assert stored.attachments[0].data is None
    assert store.get(key) == PNG_BYTES

    serialized = json.dumps(stored.model_dump())
    assert key in serialized
    assert PNG_BASE64 not in serialized
    assert ToolResult(**json.loads(serialized)) == stored


def test_next_turn_hydrates_tool_result_image_from_store(
    monkeypatch: pytest.MonkeyPatch,
):
    png = Attachment(media_type="image/png", data=PNG_BYTES)
    loop, scripted, _ = _loop(monkeypatch, png, InMemoryAttachmentStore())

    loop.run(THREAD, "покажи график")
    loop.run(THREAD, "а что на нём?")

    tool_result = _sent_tool_result(scripted.calls[-1])
    assert tool_result["content"] == [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": PNG_BASE64},
        },
    ]


def test_string_result_stays_plain_string(monkeypatch: pytest.MonkeyPatch):
    loop, scripted, memory = _loop(monkeypatch, "42", None)

    loop.run(THREAD, "сколько?")

    assert _sent_tool_result(scripted.calls[1]) == {
        "type": "tool_result",
        "tool_use_id": "call_1",
        "content": "42",
    }
    assert _stored_tool_result(memory).attachments is None


def test_image_without_attachment_store_is_rejected(monkeypatch: pytest.MonkeyPatch):
    png = Attachment(media_type="image/png", data=PNG_BYTES)
    loop, _, _ = _loop(monkeypatch, png, None)

    with pytest.raises(ValueError, match="attachment_store"):
        loop.run(THREAD, "покажи график")


def test_pdf_in_tool_result_becomes_error_result(monkeypatch: pytest.MonkeyPatch):
    pdf = Attachment(media_type="application/pdf", data=b"%PDF-1.7")
    loop, scripted, _ = _loop(monkeypatch, pdf, InMemoryAttachmentStore())

    loop.run(THREAD, "покажи отчёт")

    assert _sent_tool_result(scripted.calls[1])["is_error"] is True


def test_legacy_tool_result_row_without_attachments_reads():
    legacy = {"tool_call_id": "call_1", "content": "42", "is_error": False}

    assert ToolResult(**legacy).attachments is None
