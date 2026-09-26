from __future__ import annotations

from pydantic import BaseModel

from ai_framework.entities.attachment import Attachment


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object]


class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False
    attachments: list[Attachment] | None = None

    @classmethod
    def from_output(cls, tool_call_id: str, output: object) -> ToolResult:
        if isinstance(output, Attachment):
            return cls(
                tool_call_id=tool_call_id,
                content="",
                attachments=[_require_image(output)],
            )
        if isinstance(output, list) and any(isinstance(item, Attachment) for item in output):
            texts: list[str] = []
            attachments: list[Attachment] = []
            for item in output:
                if isinstance(item, Attachment):
                    attachments.append(_require_image(item))
                elif isinstance(item, str):
                    texts.append(item)
                else:
                    raise ValueError(
                        f"Tool result list mixes attachments with {type(item).__name__}: "
                        "only str and Attachment are allowed"
                    )
            return cls(
                tool_call_id=tool_call_id,
                content="\n".join(texts),
                attachments=attachments,
            )
        return cls(tool_call_id=tool_call_id, content=str(output))


def _require_image(attachment: Attachment) -> Attachment:
    if not attachment.media_type.startswith("image/"):
        raise ValueError(
            f"Attachment {attachment.filename or attachment.key!r} has media type "
            f"{attachment.media_type}, which is not supported in a tool result: "
            "only images are, rasterize it to PNG"
        )
    return attachment
