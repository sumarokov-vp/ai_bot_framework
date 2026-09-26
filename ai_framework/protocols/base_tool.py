from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from ai_framework.entities.attachment import Attachment
from ai_framework.entities.tool_context import ToolContext

type ToolOutput = str | Attachment | list[str | Attachment]


class BaseTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    suppress_response: ClassVar[bool] = False

    Input: ClassVar[type[BaseModel]]

    @property
    def input_schema(self) -> dict[str, Any]:
        schema = self.Input.model_json_schema()
        schema.pop("title", None)
        return schema

    @abstractmethod
    def execute(self, input, context: ToolContext) -> ToolOutput | object:  # noqa: ANN001
        ...
