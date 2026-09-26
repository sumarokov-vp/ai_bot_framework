from __future__ import annotations

import asyncio
import base64
from typing import Any, ClassVar

import pytest

pytest.importorskip("claude_agent_sdk")

from pydantic import BaseModel

from ai_framework.entities.attachment import Attachment
from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool, ToolOutput
from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-payload"


class _NoInput(BaseModel):
    pass


class _ReturningTool(BaseTool):
    name: ClassVar[str] = "show"
    description: ClassVar[str] = "Returns a prepared result"
    suppress_response: ClassVar[bool] = True
    Input: ClassVar[type[BaseModel]] = _NoInput

    def __init__(self, result: ToolOutput) -> None:
        self._result = result

    def execute(self, input: _NoInput, context: ToolContext) -> ToolOutput:  # noqa: ANN001, A002
        return self._result


def _call(result: ToolOutput) -> tuple[dict[str, Any], set[str]]:
    provider = ClaudeSdkProvider()
    wrapper = provider._wrap_tool(_ReturningTool(result))
    handler = getattr(wrapper, "handler", wrapper)
    suppressing: set[str] = set()

    async def _runner() -> dict[str, Any]:
        provider._context_var.set({})
        provider._suppressing_tools_var.set(suppressing)
        return await handler({})

    return asyncio.run(_runner()), suppressing


def test_text_and_png_become_text_and_image_content():
    png = Attachment(media_type="image/png", filename="scan.png", data=PNG_BYTES)

    result, suppressing = _call(["Скан письма", png])

    assert "isError" not in result
    assert result["content"] == [
        {"type": "text", "text": "Скан письма"},
        {
            "type": "image",
            "data": base64.standard_b64encode(PNG_BYTES).decode("ascii"),
            "mimeType": "image/png",
        },
    ]
    assert base64.standard_b64decode(result["content"][1]["data"]) == PNG_BYTES
    assert suppressing == {"show"}


def test_single_attachment_becomes_image_content():
    png = Attachment(media_type="image/png", data=PNG_BYTES)

    result, _ = _call(png)

    assert [block["type"] for block in result["content"]] == ["image"]


def test_string_result_stays_single_text_block():
    result, _ = _call("plain")

    assert result == {"content": [{"type": "text", "text": "plain"}]}


def test_pdf_attachment_is_reported_as_tool_error():
    pdf = Attachment(media_type="application/pdf", filename="scan.pdf", data=b"%PDF-1.4")

    result, suppressing = _call(["text", pdf])

    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "application/pdf" in text
    assert "not supported" in text
    assert suppressing == set()


def test_attachment_without_data_is_reported_as_tool_error():
    result, _ = _call(Attachment(media_type="image/png", key="k1"))

    assert result["isError"] is True
    assert "has no data" in result["content"][0]["text"]
