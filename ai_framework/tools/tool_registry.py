from __future__ import annotations

from ai_framework.entities.tool import ToolResult
from ai_framework.entities.tool_context import ToolContext
from ai_framework.protocols.base_tool import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def execute(
        self,
        name: str,
        arguments: dict[str, object],
        tool_call_id: str,
        tool_context: dict[str, object] | None = None,
    ) -> ToolResult:
        tool = self._tools[name]
        context = ToolContext(tool_context)
        parsed_input = tool.Input.model_validate(arguments)
        result = tool.execute(parsed_input, context)
        return ToolResult(
            tool_call_id=tool_call_id,
            content=str(result),
        )
