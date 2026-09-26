from __future__ import annotations

import logging
import os
import shutil
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import AssistantMessage, ToolUseBlock  # noqa: E402

from ai_framework.entities.tool_context import ToolContext  # noqa: E402
from ai_framework.memory.in_memory_store import InMemoryStore  # noqa: E402
from ai_framework.protocols.base_tool import BaseTool  # noqa: E402
from ai_framework.providers import claude_sdk_provider  # noqa: E402
from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider  # noqa: E402
from ai_framework.session.in_memory_session_store import InMemorySessionStore  # noqa: E402
from ai_framework.tool_loop import ToolLoop  # noqa: E402
from ai_framework.tools.tool_registry_factory import create_tool_registry  # noqa: E402

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5"
TOOL_NAME = "wiki_create_page"
PAGE_TITLE = "PAPAYA-42"
SYSTEM_PROMPT = (
    "You are a wiki assistant. When the user asks to create a page, "
    "call the page creation tool listed below. Answer in one short line."
)
REQUEST = f"Создай страницу вики с заголовком {PAGE_TITLE}."

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("AI_FRAMEWORK_LIVE_SDK") is None,
        reason="AI_FRAMEWORK_LIVE_SDK is required",
    ),
    pytest.mark.skipif(
        shutil.which("claude") is None, reason="claude CLI is required"
    ),
]


class _PageInput(BaseModel):
    title: str


class _CreatePageTool(BaseTool):
    name: ClassVar[str] = TOOL_NAME
    description: ClassVar[str] = "Create a wiki page with the given title"
    Input: ClassVar[type[BaseModel]] = _PageInput

    def __init__(self) -> None:
        self.created_titles: list[str] = []

    def execute(self, input: _PageInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        self.created_titles.append(input.title)
        return f"Page {input.title} created"


def test_claude_sdk_model_calls_tool_by_its_mcp_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sdk_messages: list[Any] = []
    real_query = claude_sdk_provider.query

    async def recording_query(**kwargs: Any) -> AsyncIterator[Any]:
        async for message in real_query(**kwargs):
            sdk_messages.append(message)
            yield message

    monkeypatch.setattr(claude_sdk_provider, "query", recording_query)

    tool = _CreatePageTool()
    provider = ClaudeSdkProvider(model=MODEL)
    loop = ToolLoop(
        provider=provider,
        memory=InMemoryStore(),
        sessions=InMemorySessionStore(),
        tool_registry=create_tool_registry([tool]),
        system_prompt=SYSTEM_PROMPT,
    )

    answer = loop.run("live-tool-names", REQUEST).content
    logger.info("answer: %s", answer)

    tool_use_names = [
        block.name
        for message in sdk_messages
        if isinstance(message, AssistantMessage)
        for block in message.content
        if isinstance(block, ToolUseBlock)
    ]
    logger.info("tool uses: %s", tool_use_names)

    assert tool.created_titles
    assert PAGE_TITLE in tool.created_titles[0]
    assert provider.model_tool_name(TOOL_NAME) in tool_use_names
    assert TOOL_NAME not in tool_use_names
    assert not any("No such tool available" in repr(m) for m in sdk_messages)
