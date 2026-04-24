from __future__ import annotations

from typing import Any

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.provider import Provider
from ai_framework.infrastructure_factory import InfrastructureContext, open_infrastructure
from ai_framework.providers.provider_factory import create_provider
from ai_framework.tool_loop import ToolLoop
from ai_framework.protocols.base_tool import BaseTool
from ai_framework.tools.tool_registry_factory import create_tool_registry


class AIApplication:
    def __init__(
        self,
        api_key: str,
        system_prompt: str,
        database_url: str,
        tools: list[BaseTool],
        model: str = "claude-sonnet-4-20250514",
        provider: Provider = Provider.ANTHROPIC,
        max_tool_rounds: int = 10,
        history_turns_limit: int | None = None,
    ) -> None:
        self._provider = create_provider(provider, api_key, model)
        self._system_prompt = system_prompt
        self._max_tool_rounds = max_tool_rounds
        self._history_turns_limit = history_turns_limit
        self._database_url = database_url
        self._tool_registry = create_tool_registry(tools)
        self._infrastructure: InfrastructureContext | None = None
        self._tool_loop: ToolLoop | None = None

    def __enter__(self) -> AIApplication:
        self._infrastructure = open_infrastructure(self._database_url)
        self._tool_loop = ToolLoop(
            provider=self._provider,
            memory=self._infrastructure.memory,
            sessions=self._infrastructure.sessions,
            tool_registry=self._tool_registry,
            system_prompt=self._system_prompt,
            max_rounds=self._max_tool_rounds,
            history_turns_limit=self._history_turns_limit,
        )
        return self

    def __exit__(self, *args: object) -> None:
        if self._infrastructure:
            self._infrastructure.close()

    @property
    def _loop(self) -> ToolLoop:
        if not self._tool_loop:
            raise RuntimeError("Use 'with app:' context manager before using AIApplication")
        return self._tool_loop

    def update_system_prompt(self, text: str) -> None:
        self._system_prompt = text
        if self._tool_loop:
            self._tool_loop.update_system_prompt(text)

    def clear_context(self, thread_id: str) -> None:
        if not self._infrastructure:
            raise RuntimeError("Use 'with app:' context manager before using AIApplication")
        self._infrastructure.memory.clear(thread_id)

    def process_message(
        self,
        thread_id: str,
        user_message: str,
        tool_context: dict[str, Any] | None = None,
    ) -> AIResponse:
        return self._loop.run(thread_id, user_message, tool_context)
