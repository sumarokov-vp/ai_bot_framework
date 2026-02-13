from __future__ import annotations

from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.tool_definition import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, object]) -> ToolResult:
        tool = self._tools[name]
        if tool.handler is None:
            raise ValueError(f"Tool '{name}' has no handler")
        result = tool.handler(**arguments)
        return ToolResult(
            tool_call_id="",
            content=str(result),
        )
