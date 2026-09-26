from __future__ import annotations

from typing import Any

import pytest

from ai_framework.attachments import CachedAttachmentStore, InMemoryAttachmentStore
from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.attachment import Attachment
from ai_framework.entities.message import Message
from ai_framework.memory.in_memory_store import InMemoryStore
from ai_framework.session.in_memory_session_store import InMemorySessionStore
from ai_framework.tool_loop import ToolLoop


class _CountingStore:
    def __init__(self) -> None:
        self._inner = InMemoryAttachmentStore()
        self.get_calls = 0

    def put(self, data: bytes, media_type: str) -> str:
        return self._inner.put(data, media_type)

    def get(self, key: str) -> bytes:
        self.get_calls += 1
        return self._inner.get(key)


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[list[Message]] = []

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: Any = None,
        tool_context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AIResponse:
        self.calls.append(messages)
        return AIResponse(content="ok")


class _NoTools:
    def get_tools(self) -> list[Any]:
        return []

    def execute(self, name: str, arguments: dict[str, Any], tool_call_id: str, tool_context: Any = None) -> Any:  # pragma: no cover
        raise NotImplementedError


def _loop(
    provider: _RecordingProvider,
    memory: InMemoryStore,
    store: Any,
) -> ToolLoop:
    return ToolLoop(
        provider=provider,
        memory=memory,
        sessions=InMemorySessionStore(),
        tool_registry=_NoTools(),
        system_prompt="sys",
        attachment_store=store,
    )


def test_tool_loop_stores_key_in_memory_and_hydrates_provider():
    provider = _RecordingProvider()
    memory = InMemoryStore()
    loop = _loop(provider, memory, InMemoryAttachmentStore())
    photo = b"\xff\xd8\xff-jpeg-bytes"

    loop.run(
        "t1",
        "что на фото?",
        attachments=[Attachment(media_type="image/jpeg", data=photo, filename="IMG.jpg")],
    )
    loop.run("t1", "а ещё?")

    stored = memory.get_messages("t1")[0].attachments
    assert stored is not None
    assert stored[0].data is None
    assert stored[0].key is not None and stored[0].key.endswith(".jpg")
    assert stored[0].filename == "IMG.jpg"
    for sent in provider.calls:
        sent_attachments = sent[0].attachments
        assert sent_attachments is not None
        assert sent_attachments[0].data == photo
    assert memory.get_messages("t1")[0].attachments == stored


def test_tool_loop_without_attachments_and_store_works_as_before():
    provider = _RecordingProvider()
    memory = InMemoryStore()

    _loop(provider, memory, None).run("t1", "hi")

    assert provider.calls[0][0] == Message(role="user", content="hi")


def test_tool_loop_attachments_without_store_fail_before_model_call():
    provider = _RecordingProvider()
    memory = InMemoryStore()

    with pytest.raises(ValueError, match="attachment_store"):
        _loop(provider, memory, None).run(
            "t1", "hi", attachments=[Attachment(media_type="image/png", data=b"x")]
        )

    assert provider.calls == []
    assert memory.get_messages("t1") == []


def test_cached_store_second_get_does_not_hit_inner():
    inner = _CountingStore()
    key = inner.put(b"abc", "image/png")
    cached = CachedAttachmentStore(inner)

    assert cached.get(key) == b"abc"
    assert cached.get(key) == b"abc"
    assert inner.get_calls == 1


def test_cached_store_put_caches_immediately():
    inner = _CountingStore()
    cached = CachedAttachmentStore(inner)

    key = cached.put(b"abc", "application/pdf")

    assert cached.get(key) == b"abc"
    assert inner.get_calls == 0


def test_cached_store_evicts_oldest_beyond_max_bytes():
    inner = _CountingStore()
    cached = CachedAttachmentStore(inner, max_bytes=10)
    first = cached.put(b"12345", "image/png")
    second = cached.put(b"67890", "image/png")
    cached.get(first)

    third = cached.put(b"abcde", "image/png")

    assert cached.get(first) == b"12345"
    assert cached.get(third) == b"abcde"
    assert inner.get_calls == 0
    assert cached.get(second) == b"67890"
    assert inner.get_calls == 1
