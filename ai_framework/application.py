from __future__ import annotations

import logging

from typing import Any

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.provider import Provider
from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.i_memory_store import IMemoryStore
from ai_framework.protocols.i_session_store import ISessionStore
from ai_framework.protocols.tool_definition import ToolDefinition


logger = logging.getLogger(__name__)


class AIApplication:
    def __init__(
        self,
        api_key: str,
        system_prompt: str,
        database_url: str,
        tools: list[ToolDefinition],
        model: str = "claude-sonnet-4-20250514",
        provider: Provider = Provider.ANTHROPIC,
        max_tool_rounds: int = 10,
    ) -> None:
        self._provider = self._create_provider(provider, api_key, model)
        self._system_prompt = system_prompt
        self._max_tool_rounds = max_tool_rounds
        self._database_url = database_url

        self._memory: IMemoryStore | None = None
        self._session_store: ISessionStore | None = None

        from ai_framework.tools.tool_registry import ToolRegistry

        registry = ToolRegistry()
        for tool in tools:
            registry.register(tool)
        self._tool_registry = registry

    @staticmethod
    def _create_provider(
        provider: Provider, api_key: str, model: str,
    ) -> Any:
        if provider == Provider.ANTHROPIC:
            from ai_framework.providers.anthropic_provider import AnthropicProvider

            return AnthropicProvider(api_key=api_key, model=model)
        if provider == Provider.CLAUDE_SDK:
            from ai_framework.providers.claude_sdk_provider import ClaudeSdkProvider

            return ClaudeSdkProvider(model=model)
        raise ValueError(f"Unknown provider: {provider}")

    def open(self) -> None:
        from ai_framework.memory.postgres_memory_store import PostgresMemoryStore
        from ai_framework.migrations import apply_migrations
        from ai_framework.session.postgres_session_store import PostgresSessionStore

        apply_migrations(self._database_url)

        self._memory = PostgresMemoryStore(self._database_url)
        self._memory.open()

        self._session_store = PostgresSessionStore(self._database_url)
        self._session_store.open()

    def close(self) -> None:
        if self._session_store:
            self._session_store.close()
        if self._memory:
            self._memory.close()

    def __enter__(self) -> AIApplication:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def _store(self) -> IMemoryStore:
        if not self._memory:
            raise RuntimeError("Call open() before using AIApplication")
        return self._memory

    @property
    def _sessions(self) -> ISessionStore:
        if not self._session_store:
            raise RuntimeError("Call open() before using AIApplication")
        return self._session_store

    def update_system_prompt(self, text: str) -> None:
        self._system_prompt = text

    def clear_context(self, thread_id: str) -> None:
        self._store.clear(thread_id)

    def process_message(
        self,
        thread_id: str,
        user_message: str,
        tool_context: dict[str, Any] | None = None,
    ) -> AIResponse:
        self._sessions.get_or_create(thread_id)
        self._sessions.touch(thread_id)

        user_msg = Message(role="user", content=user_message)
        self._store.add_message(thread_id, user_msg)

        tools = self._tool_registry.get_definitions() or None

        for _ in range(self._max_tool_rounds):
            messages = self._store.get_messages(thread_id)
            response = self._provider.send_message(
                messages=messages,
                system=self._system_prompt,
                tools=tools,
            )

            if not response.tool_calls:
                break

            assistant_msg = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
            self._store.add_message(thread_id, assistant_msg)

            tool_results = self._execute_tool_calls(response, tool_context)
            tool_msg = Message(
                role="user",
                content="",
                tool_results=tool_results,
            )
            self._store.add_message(thread_id, tool_msg)
        else:
            raise RuntimeError(
                f"Tool loop exceeded {self._max_tool_rounds} rounds"
            )

        assistant_msg = Message(
            role="assistant",
            content=response.content or "",
        )
        self._store.add_message(thread_id, assistant_msg)
        return response

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
            logger.info(
                "Tool result: %s -> %s", tool_call.name, result.content
            )
            results.append(result)
        return results
