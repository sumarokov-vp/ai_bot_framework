from __future__ import annotations

import logging
import os
import shutil
import struct
import zlib
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

pytest.importorskip("claude_agent_sdk")

from ai_framework import Attachment  # noqa: E402
from ai_framework.attachments.in_memory_attachment_store import (  # noqa: E402
    InMemoryAttachmentStore,
)
from ai_framework.entities.tool_context import ToolContext  # noqa: E402
from ai_framework.memory.in_memory_store import InMemoryStore  # noqa: E402
from ai_framework.protocols.base_tool import BaseTool  # noqa: E402
from ai_framework.protocols.i_ai_provider import IAIProvider  # noqa: E402
from ai_framework.providers.anthropic_provider import AnthropicProvider  # noqa: E402
from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider  # noqa: E402
from ai_framework.session.in_memory_session_store import InMemorySessionStore  # noqa: E402
from ai_framework.tool_loop import ToolLoop  # noqa: E402
from ai_framework.tools.tool_registry_factory import create_tool_registry  # noqa: E402

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
TOOL_NAME = "fetch_scan"
IMAGE_WORD = "MANGO"
SYSTEM_PROMPT = (
    "You are a terse assistant. To see the scan, call the scan tool listed below. "
    "Answer in one short line."
)
REQUEST = (
    "Достань скан инструментом и скажи, какое слово на нём написано. "
    "Ответь дословно, теми же латинскими буквами, без перевода и транслитерации."
)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

pytestmark = pytest.mark.skipif(
    os.environ.get("AI_FRAMEWORK_LIVE_SDK") is None,
    reason="AI_FRAMEWORK_LIVE_SDK is required",
)

GLYPHS: dict[str, tuple[str, ...]] = {
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def render_word_png(word: str, scale: int = 16, margin: int = 2) -> bytes:
    cells = [""] * 7
    for index, letter in enumerate(word):
        for line_number in range(7):
            cells[line_number] += ("0" if index else "") + GLYPHS[letter][line_number]
    padded = (
        ["0" * (len(cells[0]) + 2 * margin)] * margin
        + ["0" * margin + row + "0" * margin for row in cells]
        + ["0" * (len(cells[0]) + 2 * margin)] * margin
    )
    raw = b""
    for pixels in padded:
        line = b"".join(
            (b"\x00" if cell == "1" else b"\xff") * scale for cell in pixels
        )
        raw += (b"\x00" + line) * scale
    width = len(padded[0]) * scale
    height = len(padded) * scale
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


class _NoInput(BaseModel):
    pass


class _ScanTool(BaseTool):
    name: ClassVar[str] = TOOL_NAME
    description: ClassVar[str] = "Fetch the scanned page as an image"
    Input: ClassVar[type[BaseModel]] = _NoInput

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, input: _NoInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        self.calls += 1
        return [
            "Scan of the page:",
            Attachment(
                media_type="image/png",
                filename="scan.png",
                data=render_word_png(IMAGE_WORD),
            ),
        ]


def _run(provider: IAIProvider, thread_id: str) -> tuple[_ScanTool, str]:
    tool = _ScanTool()
    loop = ToolLoop(
        provider=provider,
        memory=InMemoryStore(),
        sessions=InMemorySessionStore(),
        tool_registry=create_tool_registry([tool]),
        system_prompt=SYSTEM_PROMPT,
        attachment_store=InMemoryAttachmentStore(),
    )
    return tool, loop.run(thread_id, REQUEST).content or ""


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI is required")
def test_claude_sdk_reads_word_from_tool_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    tool, answer = _run(ClaudeSdkProvider(model=MODEL), "live-tool-image-sdk")
    logger.info("ClaudeSdkProvider: %r (вызовов инструмента: %s)", answer, tool.calls)
    assert tool.calls >= 1
    assert IMAGE_WORD.lower() in answer.lower()


@pytest.mark.skipif(ANTHROPIC_API_KEY is None, reason="ANTHROPIC_API_KEY is not set")
def test_anthropic_reads_word_from_tool_image() -> None:
    assert ANTHROPIC_API_KEY is not None
    tool, answer = _run(
        AnthropicProvider(api_key=ANTHROPIC_API_KEY, model=MODEL),
        "live-tool-image-api",
    )
    logger.info("AnthropicProvider: %r (вызовов инструмента: %s)", answer, tool.calls)
    assert tool.calls >= 1
    assert IMAGE_WORD.lower() in answer.lower()
