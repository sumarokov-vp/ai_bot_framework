from __future__ import annotations

import base64

from types import SimpleNamespace
from typing import Any

import pytest

from ai_framework import Attachment, Message
from ai_framework.providers.anthropic_provider import AnthropicProvider


JPEG_BYTES = b"\xff\xd8\xff\xe0-fake-jpeg"
PDF_BYTES = b"%PDF-1.7 fake pdf"


class RecordingMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


@pytest.fixture
def recorded() -> RecordingMessages:
    return RecordingMessages()


@pytest.fixture
def provider(
    monkeypatch: pytest.MonkeyPatch, recorded: RecordingMessages
) -> AnthropicProvider:
    instance = AnthropicProvider(api_key="test-key")
    monkeypatch.setattr(instance, "_client", SimpleNamespace(messages=recorded))
    return instance


def test_jpeg_with_text_becomes_image_then_text_blocks(
    provider: AnthropicProvider, recorded: RecordingMessages
):
    message = Message(
        role="user",
        content="Когда истекает паспорт?",
        attachments=[
            Attachment(media_type="image/jpeg", data=JPEG_BYTES, key="k1.jpg")
        ],
    )

    provider.send_message([message])

    sent = recorded.calls[0]["messages"][0]
    assert sent["role"] == "user"
    assert [block["type"] for block in sent["content"]] == ["image", "text"]
    image_block = sent["content"][0]
    assert image_block["source"] == {
        "type": "base64",
        "media_type": "image/jpeg",
        "data": base64.standard_b64encode(JPEG_BYTES).decode("ascii"),
    }
    assert sent["content"][1] == {"type": "text", "text": "Когда истекает паспорт?"}


def test_pdf_without_text_becomes_single_document_block(
    provider: AnthropicProvider, recorded: RecordingMessages
):
    message = Message(
        role="user",
        content="",
        attachments=[
            Attachment(media_type="application/pdf", data=PDF_BYTES, key="k2.pdf")
        ],
    )

    provider.send_message([message])

    content = recorded.calls[0]["messages"][0]["content"]
    assert len(content) == 1
    document_block = content[0]
    assert document_block["type"] == "document"
    assert document_block["source"]["media_type"] == "application/pdf"
    assert base64.standard_b64decode(document_block["source"]["data"]) == PDF_BYTES


def test_attachment_without_data_raises_with_key(
    provider: AnthropicProvider, recorded: RecordingMessages
):
    message = Message(
        role="user",
        content="что тут?",
        attachments=[Attachment(media_type="image/png", key="missing.png")],
    )

    with pytest.raises(ValueError, match="missing.png"):
        provider.send_message([message])
    assert recorded.calls == []


def test_message_without_attachments_keeps_string_content(
    provider: AnthropicProvider, recorded: RecordingMessages
):
    provider.send_message([Message(role="user", content="привет")])

    assert recorded.calls[0]["messages"] == [{"role": "user", "content": "привет"}]
