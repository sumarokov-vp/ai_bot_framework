from __future__ import annotations

from typing import Any

import pytest

from ai_framework.entities.message import Message
from ai_framework.entities.tool import ToolCall, ToolResult
from ai_framework.tool_loop import ToolLoop


class _StubProvider:
    def send_message(self, **kwargs: Any) -> Any:  # pragma: no cover
        raise NotImplementedError


class _StubMemory:
    def get_messages(self, thread_id: str) -> list[Message]:  # pragma: no cover
        return []

    def add_message(self, thread_id: str, message: Message) -> None:  # pragma: no cover
        pass

    def clear(self, thread_id: str) -> None:  # pragma: no cover
        pass


class _StubSessions:
    def get_or_create(self, thread_id: str) -> Any:  # pragma: no cover
        return None

    def touch(self, thread_id: str) -> None:  # pragma: no cover
        pass


class _StubRegistry:
    def get_tools(self) -> list[Any]:
        return []

    def execute(self, name: str, arguments: dict[str, Any], call_id: str, tool_context: Any = None) -> Any:  # pragma: no cover
        raise NotImplementedError


def _make_loop(limit: int | None) -> ToolLoop:
    return ToolLoop(
        provider=_StubProvider(),
        memory=_StubMemory(),
        sessions=_StubSessions(),
        tool_registry=_StubRegistry(),
        system_prompt="sys",
        history_turns_limit=limit,
    )


def _user(text: str) -> Message:
    return Message(role="user", content=text)


def _assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def _assistant_with_tool(text: str, tool_name: str, call_id: str) -> Message:
    return Message(
        role="assistant",
        content=text,
        tool_calls=[ToolCall(id=call_id, name=tool_name, arguments={})],
    )


def _tool_result(call_id: str, content: str) -> Message:
    return Message(
        role="user",
        content="",
        tool_results=[ToolResult(tool_call_id=call_id, content=content)],
    )


def test_trim_returns_all_when_limit_none():
    loop = _make_loop(None)
    messages = [
        _user("hi"),
        _assistant("hello"),
        _user("how are you?"),
        _assistant("fine"),
    ]

    assert loop._trim_history(messages) == messages


def test_trim_keeps_last_two_of_three_turns():
    loop = _make_loop(2)
    turn1 = [_user("q1"), _assistant("a1")]
    turn2 = [_user("q2"), _assistant("a2")]
    turn3 = [_user("q3"), _assistant("a3")]
    messages = turn1 + turn2 + turn3

    result = loop._trim_history(messages)

    assert result == turn2 + turn3
    assert result[0].role == "user"
    assert not result[0].tool_results


def test_trim_returns_all_when_fewer_turns_than_limit():
    loop = _make_loop(5)
    messages = [_user("q1"), _assistant("a1")]

    assert loop._trim_history(messages) == messages


def test_trim_preserves_tool_use_result_pairing():
    loop = _make_loop(1)
    turn1 = [
        _user("q1"),
        _assistant_with_tool("", "search", "call_1"),
        _tool_result("call_1", "res1"),
        _assistant("a1"),
    ]
    turn2 = [
        _user("q2"),
        _assistant_with_tool("", "search", "call_2"),
        _tool_result("call_2", "res2"),
        _assistant("a2"),
    ]
    messages = turn1 + turn2

    result = loop._trim_history(messages)

    assert result == turn2
    assert len(result) == 4
    assert result[0].role == "user"
    assert not result[0].tool_results
    assert result[1].tool_calls is not None
    assert result[2].tool_results is not None
    assert result[1].tool_calls[0].id == result[2].tool_results[0].tool_call_id


def test_zero_limit_raises_value_error():
    with pytest.raises(ValueError):
        _make_loop(0)


def test_trim_empty_messages_returns_empty():
    loop = _make_loop(3)
    assert loop._trim_history([]) == []
