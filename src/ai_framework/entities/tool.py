from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object]


class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False
