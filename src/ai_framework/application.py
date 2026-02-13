from __future__ import annotations

from ai_framework.entities.ai_response import AIResponse
from ai_framework.entities.message import Message
from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.i_ai_provider import IAIProvider
from ai_framework.protocols.i_memory_store import IMemoryStore
from ai_framework.protocols.i_tool_registry import IToolRegistry


class AIApplication:
    def __init__(
        self,
        provider: IAIProvider,
        memory: IMemoryStore,
        tool_registry: IToolRegistry | None = None,
        system_prompt: str | None = None,
        max_tool_rounds: int = 10,
    ) -> None:
        self._provider = provider
        self._memory = memory
        self._tool_registry = tool_registry
        self._system_prompt = system_prompt
        self._max_tool_rounds = max_tool_rounds

    def process_message(self, thread_id: str, user_message: str) -> AIResponse:
        user_msg = Message(role="user", content=user_message)
        self._memory.add_message(thread_id, user_msg)

        tools = self._tool_registry.get_definitions() if self._tool_registry else None

        for _ in range(self._max_tool_rounds):
            messages = self._memory.get_messages(thread_id)
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
            self._memory.add_message(thread_id, assistant_msg)

            tool_results = self._execute_tool_calls(response)
            tool_msg = Message(
                role="user",
                content="",
                tool_results=tool_results,
            )
            self._memory.add_message(thread_id, tool_msg)
        else:
            raise RuntimeError(
                f"Tool loop exceeded {self._max_tool_rounds} rounds"
            )

        assistant_msg = Message(
            role="assistant",
            content=response.content or "",
        )
        self._memory.add_message(thread_id, assistant_msg)
        return response

    def _execute_tool_calls(self, response: AIResponse) -> list[ToolResult]:
        if not self._tool_registry:
            raise ValueError("Tool registry is required to execute tool calls")

        results: list[ToolResult] = []
        for tool_call in response.tool_calls:
            result = self._tool_registry.execute(tool_call.name, tool_call.arguments)
            results.append(
                ToolResult(
                    tool_call_id=tool_call.id,
                    content=result.content,
                    is_error=result.is_error,
                )
            )
        return results
