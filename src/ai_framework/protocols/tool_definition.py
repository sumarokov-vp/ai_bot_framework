from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any] | None = None
    context_params: list[str] = []
