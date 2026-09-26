from __future__ import annotations

import base64

import pytest

from pydantic import ValidationError

from ai_framework import Attachment, Message


PNG_BYTES = b"\x89PNG\r\n\x1a\n-fake-png"
PDF_BYTES = b"%PDF-1.7 fake pdf"


def test_data_is_not_serialized():
    attachment = Attachment(
        media_type="image/jpeg", data=b"secret-bytes", filename="IMG.jpg", key="k1.jpg"
    )

    dumped = attachment.model_dump_json()

    assert "data" not in dumped
    assert "secret-bytes" not in dumped
    restored = Attachment.model_validate_json(dumped)
    assert restored.key == "k1.jpg"
    assert restored.media_type == "image/jpeg"
    assert restored.filename == "IMG.jpg"
    assert restored.data is None


def test_data_is_not_serialized_inside_message():
    message = Message(
        role="user",
        content="hi",
        attachments=[Attachment(media_type="image/png", data=PNG_BYTES, key="k.png")],
    )

    dumped = message.model_dump(mode="json")

    assert dumped["attachments"] == [
        {"media_type": "image/png", "filename": None, "key": "k.png"}
    ]


def test_unsupported_media_type_is_rejected():
    with pytest.raises(ValidationError):
        Attachment.model_validate({"media_type": "image/tiff", "data": b"x"})


def test_png_content_block():
    block = Attachment(media_type="image/png", data=PNG_BYTES).to_content_block()

    assert block == {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(PNG_BYTES).decode("ascii"),
        },
    }


def test_pdf_content_block():
    block = Attachment(media_type="application/pdf", data=PDF_BYTES).to_content_block()

    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"
    assert base64.standard_b64decode(block["source"]["data"]) == PDF_BYTES


def test_content_block_without_data_names_key():
    with pytest.raises(ValueError, match="k-missing.pdf"):
        Attachment(media_type="application/pdf", key="k-missing.pdf").to_content_block()
