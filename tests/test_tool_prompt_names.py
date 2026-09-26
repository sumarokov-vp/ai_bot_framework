from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic import BaseModel

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.tool_context import ToolContext
from ai_framework.memory.in_memory_store import InMemoryStore
from ai_framework.protocols.base_tool import BaseTool
from ai_framework.providers.anthropic_provider import AnthropicProvider
from ai_framework.session.in_memory_session_store import InMemorySessionStore
from ai_framework.tool_loop import ToolLoop
from ai_framework.tools.tool_registry_factory import create_tool_registry

SYSTEM_PROMPT = "You are a wiki assistant."


class _PageInput(BaseModel):
    title: str


class _CreatePageTool(BaseTool):
    name: ClassVar[str] = "wiki_create_page"
    description: ClassVar[str] = "Create a wiki page"
    Input: ClassVar[type[BaseModel]] = _PageInput

    def execute(self, input: _PageInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        return "created"


class _CreateTaskTool(BaseTool):
    name: ClassVar[str] = "create_task"
    description: ClassVar[str] = "Create a task"
    Input: ClassVar[type[BaseModel]] = _PageInput

    def execute(self, input: _PageInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        return "created"


PRE_FIX_SYSTEM = (
    SYSTEM_PROMPT
    + "\n\n## Available tools\n\n"
    + "- **wiki_create_page**: Create a wiki page\n"
    + "- **create_task**: Create a task"
)


class _SystemRecorder:
    def __init__(self) -> None:
        self.systems: list[str | None] = []

    def send_message(
        self,
        messages: list[Message],
        system: str | None = None,
        tools: Any = None,
        tool_context: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> AIResponse:
        self.systems.append(system)
        return AIResponse(content="ok")


class _SdkNamedProvider(_SystemRecorder):
    def __init__(self, mcp_server_name: str = "ai-framework-tools") -> None:
        super().__init__()
        claude_sdk_provider = pytest.importorskip(
            "ai_framework.providers.claude_sdk_provider"
        )
        self._naming = claude_sdk_provider.ClaudeSdkProvider(
            mcp_server_name=mcp_server_name
        )

    def model_tool_name(self, name: str) -> str:
        return self._naming.model_tool_name(name)


def _system_sent(provider: Any) -> str | None:
    loop = ToolLoop(
        provider=provider,
        memory=InMemoryStore(),
        sessions=InMemorySessionStore(),
        tool_registry=create_tool_registry([_CreatePageTool(), _CreateTaskTool()]),
        system_prompt=SYSTEM_PROMPT,
    )
    loop.run("t1", "заведи страницу")
    return provider.systems[0]


def test_claude_sdk_names_tools_by_mcp_name_in_system_prompt() -> None:
    system = _system_sent(_SdkNamedProvider()) or ""

    assert "- **mcp__ai-framework-tools__wiki_create_page**: Create a wiki page" in system
    assert "- **mcp__ai-framework-tools__create_task**: Create a task" in system
    assert "- **wiki_create_page**" not in system
    assert "- **create_task**" not in system


def test_claude_sdk_prompt_name_follows_mcp_server_name() -> None:
    system = _system_sent(_SdkNamedProvider(mcp_server_name="pa")) or ""

    assert "- **mcp__pa__wiki_create_page**" in system


def test_anthropic_provider_system_prompt_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AnthropicProvider(api_key="test")
    recorder = _SystemRecorder()
    monkeypatch.setattr(provider, "send_message", recorder.send_message)

    loop = ToolLoop(
        provider=provider,
        memory=InMemoryStore(),
        sessions=InMemorySessionStore(),
        tool_registry=create_tool_registry([_CreatePageTool(), _CreateTaskTool()]),
        system_prompt=SYSTEM_PROMPT,
    )
    loop.run("t1", "заведи страницу")

    assert recorder.systems[0] == PRE_FIX_SYSTEM


def test_provider_without_naming_method_keeps_bare_names() -> None:
    assert _system_sent(_SystemRecorder()) == PRE_FIX_SYSTEM
