from __future__ import annotations

from typing import Protocol

from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.tool_definition import ToolDefinition


class IToolRegistry(Protocol):
    def register(self, tool: ToolDefinition) -> None: ...

    def get_definitions(self) -> list[ToolDefinition]: ...

    def execute(self, name: str, arguments: dict[str, object]) -> ToolResult: ...
