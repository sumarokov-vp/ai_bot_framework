from __future__ import annotations

from ai_framework.protocols.tool_definition import ToolDefinition
from ai_framework.tools.tool_registry import ToolRegistry


def create_tool_registry(tools: list[ToolDefinition]) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry
