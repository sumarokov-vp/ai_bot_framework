from __future__ import annotations

from typing import Protocol

from ai_framework.entities.tool import ToolResult
from ai_framework.protocols.base_tool import BaseTool


class IToolRegistry(Protocol):
    def get_tools(self) -> list[BaseTool]: ...

    def execute(
        self,
        name: str,
        arguments: dict[str, object],
        tool_call_id: str,
        tool_context: dict[str, object] | None = None,
    ) -> ToolResult: ...
