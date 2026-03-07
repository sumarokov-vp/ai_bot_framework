from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from ai_framework.entities.tool_context import ToolContext


class BaseTool[InputT: BaseModel](ABC):
    name: ClassVar[str]
    description: ClassVar[str]

    Input: ClassVar[type[BaseModel]]

    @property
    def input_schema(self) -> dict[str, Any]:
        schema = self.Input.model_json_schema()
        schema.pop("title", None)
        return schema

    @abstractmethod
    def execute(self, input: InputT, context: ToolContext) -> Any: ...
