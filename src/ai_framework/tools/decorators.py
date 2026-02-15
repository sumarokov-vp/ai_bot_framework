from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import TypeAdapter

from ai_framework.protocols.tool_definition import ToolDefinition

_PYTHON_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _build_input_schema(func: Callable[..., Any]) -> dict[str, Any]:
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        param_type = hints.get(param_name, str)

        if param_type in _PYTHON_TYPE_TO_JSON:
            prop: dict[str, Any] = {"type": _PYTHON_TYPE_TO_JSON[param_type]}
        else:
            adapter = TypeAdapter(param_type)
            prop = adapter.json_schema()

        properties[param_name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def tool(
    name: str,
    description: str,
    context_params: list[str] | None = None,
) -> Callable[[Callable[..., Any]], ToolDefinition]:
    def decorator(func: Callable[..., Any]) -> ToolDefinition:
        input_schema = _build_input_schema(func)
        excluded = context_params or []
        if excluded:
            for param_name in excluded:
                input_schema.get("properties", {}).pop(param_name, None)
                if "required" in input_schema:
                    input_schema["required"] = [
                        r for r in input_schema["required"] if r != param_name
                    ]
        return ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
            context_params=excluded,
        )

    return decorator
