from __future__ import annotations

import logging

from typing import Any

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.i_ai_provider import IAIProvider
from ai_framework.protocols.i_memory_store import IMemoryStore
from ai_framework.protocols.i_session_store import ISessionStore
from ai_framework.protocols.i_tool_registry import IToolRegistry


logger = logging.getLogger(__name__)


class ToolLoop:
    def __init__(
        self,
        provider: IAIProvider,
        memory: IMemoryStore,
        sessions: ISessionStore,
        tool_registry: IToolRegistry,
        system_prompt: str,
        max_rounds: int = 10,
    ) -> None:
        self._provider = provider
        self._memory = memory
        self._sessions = sessions
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt
        self._max_rounds = max_rounds

    def update_system_prompt(self, text: str) -> None:
        self._system_prompt = text

    def _build_system_prompt(self, tools: list[Any] | None) -> str:
        if not tools:
            return self._system_prompt

        tool_lines = []
        for tool in tools:
            tool_lines.append(f"- **{tool.name}**: {tool.description}")

        tools_block = (
            "\n\n## Available tools\n\n"
            + "\n".join(tool_lines)
        )
        return self._system_prompt + tools_block

    def run(
        self,
        thread_id: str,
        user_message: str,
        tool_context: dict[str, Any] | None = None,
    ) -> AIResponse:
        self._sessions.get_or_create(thread_id)
        self._sessions.touch(thread_id)

        user_msg = Message(role="user", content=user_message)
        self._memory.add_message(thread_id, user_msg)

        tools = self._tool_registry.get_tools() or None
        system_prompt = self._build_system_prompt(tools)
        suppress_response = False

        for _ in range(self._max_rounds):
            messages = self._memory.get_messages(thread_id)
            response = self._provider.send_message(
                messages=messages,
                system=system_prompt,
                tools=tools,
            )

            if not response.tool_calls:
                break

            assistant_msg = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            self._memory.add_message(thread_id, assistant_msg)

            tool_results = self._execute_tool_calls(response, tool_context)
            if self._has_suppress_response_tools(response):
                suppress_response = True
            tool_msg = Message(
                role="user",
                content="",
                tool_results=tool_results,
            )
            self._memory.add_message(thread_id, tool_msg)
        else:
            raise RuntimeError(
                f"Tool loop exceeded {self._max_rounds} rounds"
            )

        assistant_msg = Message(
            role="assistant",
            content=response.content or "",
        )
        self._memory.add_message(thread_id, assistant_msg)
        response.suppress_response = suppress_response
        return response

    def _has_suppress_response_tools(self, response: AIResponse) -> bool:
        tools = {t.name: t for t in self._tool_registry.get_tools()}
        return any(
            getattr(tools.get(tc.name), "suppress_response", False)
            for tc in response.tool_calls
        )

    def _execute_tool_calls(
        self,
        response: AIResponse,
        tool_context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tool_call in response.tool_calls:
            arguments = tool_call.arguments
            logger.info(
                "Tool call: %s(%s)", tool_call.name, arguments
            )
            try:
                result = self._tool_registry.execute(
                    tool_call.name, arguments, tool_call.id,
                    tool_context=tool_context,
                )
            except Exception:
                logger.exception("Tool %s raised an exception", tool_call.name)
                result = ToolResult(
                    tool_call_id=tool_call.id,
                    content=f"Tool {tool_call.name} failed with an internal error.",
                    is_error=True,
                )
            if result.is_error:
                logger.error(
                    "Tool error: %s -> %s", tool_call.name, result.content
                )
            else:
                logger.info(
                    "Tool result: %s -> %s", tool_call.name, result.content
                )
            results.append(result)
        return results
