from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import pytest

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from ai_framework import application  # noqa: E402
from ai_framework.application import AIApplication  # noqa: E402
from ai_framework.entities.message import Message  # noqa: E402
from ai_framework.entities.provider import Provider  # noqa: E402
from ai_framework.entities.tool_context import ToolContext  # noqa: E402
from ai_framework.infrastructure_factory import InfrastructureContext  # noqa: E402
from ai_framework.memory.in_memory_store import InMemoryStore  # noqa: E402
from ai_framework.protocols.base_tool import BaseTool  # noqa: E402
from ai_framework.providers import claude_sdk_provider  # noqa: E402
from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider  # noqa: E402
from ai_framework.session.in_memory_session_store import InMemorySessionStore  # noqa: E402


class _NoteInput(BaseModel):
    text: str


class _SilentTool(BaseTool):
    name: ClassVar[str] = "silent"
    description: ClassVar[str] = "Sends the answer itself"
    suppress_response: ClassVar[bool] = True
    Input: ClassVar[type[BaseModel]] = _NoteInput

    def execute(self, input: _NoteInput, context: ToolContext) -> Any:  # noqa: ANN001, A002
        return "sent"


class _FakeSdk:
    def __init__(self) -> None:
        self.resumes: list[str | None] = []
        self.tools: dict[str, Any] = {}
        self.call_tool: str | None = None
        self._sessions_created = 0

    def create_sdk_mcp_server(
        self, name: str, version: str = "1.0.0", tools: list[Any] | None = None
    ) -> Any:
        self.tools = {t.name: t for t in tools or []}
        return {"type": "sdk", "name": name}

    def query(self, *, prompt: Any, options: Any) -> AsyncIterator[Any]:
        return self._run(options)

    async def _run(self, options: Any) -> AsyncIterator[Any]:
        self.resumes.append(options.resume)
        if self.call_tool is not None:
            handler = self.tools[self.call_tool].handler
            await asyncio.get_running_loop().create_task(handler({"text": "hi"}))
        yield AssistantMessage(content=[TextBlock(text="ok")], model="fake")
        session_id = options.resume or self._new_session_id()
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id=session_id,
        )

    def _new_session_id(self) -> str:
        self._sessions_created += 1
        return f"session-{self._sessions_created}"


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch) -> _FakeSdk:
    fake = _FakeSdk()
    monkeypatch.setattr(claude_sdk_provider, "query", fake.query)
    monkeypatch.setattr(
        claude_sdk_provider, "create_sdk_mcp_server", fake.create_sdk_mcp_server
    )
    return fake


@pytest.fixture
def in_memory_infrastructure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _open(database_url: str) -> InfrastructureContext:
        return InfrastructureContext(
            memory=InMemoryStore(), sessions=InMemorySessionStore()
        )

    monkeypatch.setattr(application, "open_infrastructure", _open)


def _user(text: str) -> list[Message]:
    return [Message(role="user", content=text)]


def test_each_thread_resumes_its_own_session(fake_sdk: _FakeSdk):
    provider = ClaudeSdkProvider()

    provider.send_message(_user("a1"), thread_id="A")
    provider.send_message(_user("b1"), thread_id="B")
    provider.send_message(_user("a2"), thread_id="A")
    provider.send_message(_user("b2"), thread_id="B")

    assert fake_sdk.resumes == [None, None, "session-1", "session-2"]
    assert provider.last_session_id == "session-2"


def test_reset_session_forgets_only_that_thread(fake_sdk: _FakeSdk):
    provider = ClaudeSdkProvider()
    provider.send_message(_user("a1"), thread_id="A")
    provider.send_message(_user("b1"), thread_id="B")

    provider.reset_session("A")
    provider.send_message(_user("a2"), thread_id="A")
    provider.send_message(_user("b2"), thread_id="B")

    assert fake_sdk.resumes == [None, None, None, "session-2"]


def test_without_thread_id_keeps_single_session(fake_sdk: _FakeSdk):
    provider = ClaudeSdkProvider()

    provider.send_message(_user("one"))
    provider.send_message(_user("two"))

    assert fake_sdk.resumes == [None, "session-1"]


def test_clear_context_resets_sdk_session_of_the_thread(
    fake_sdk: _FakeSdk, in_memory_infrastructure: None
):
    with AIApplication(
        api_key="",
        system_prompt="sys",
        database_url="unused",
        tools=[],
        provider=Provider.CLAUDE_SDK,
    ) as app:
        app.process_message("A", "a1")
        app.process_message("B", "b1")
        app.clear_context("A")
        app.process_message("A", "a2")
        app.process_message("B", "b2")

    assert fake_sdk.resumes == [None, None, None, "session-2"]


def test_suppress_response_tool_called_by_sdk_reaches_process_message(
    fake_sdk: _FakeSdk, in_memory_infrastructure: None
):
    fake_sdk.call_tool = "silent"
    with AIApplication(
        api_key="",
        system_prompt="sys",
        database_url="unused",
        tools=[_SilentTool()],
        provider=Provider.CLAUDE_SDK,
    ) as app:
        suppressed = app.process_message("A", "send it")
        fake_sdk.call_tool = None
        answered = app.process_message("A", "just talk")

    assert suppressed.suppress_response is True
    assert answered.suppress_response is False
