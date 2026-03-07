from __future__ import annotations

from ai_framework.protocols.base_tool import BaseTool
from ai_framework.tools.tool_registry import ToolRegistry


def create_tool_registry(tools: list[BaseTool]) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry
