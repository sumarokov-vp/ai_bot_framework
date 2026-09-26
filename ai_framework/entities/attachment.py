from __future__ import annotations

import base64

from typing import Any, Literal

from pydantic import BaseModel, Field


AttachmentMediaType = Literal[
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
]

ATTACHMENT_FILE_EXTENSIONS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


class Attachment(BaseModel):
    media_type: AttachmentMediaType
    filename: str | None = None
    key: str | None = None
    data: bytes | None = Field(default=None, exclude=True)

    def to_content_block(self) -> dict[str, Any]:
        block_type = "document" if self.media_type == "application/pdf" else "image"
        return {
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": self.media_type,
                "data": self._base64_data(),
            },
        }

    def to_mcp_content(self) -> dict[str, Any]:
        if not self.media_type.startswith("image/"):
            raise ValueError(
                f"Attachment {self.filename or self.key!r} has media type {self.media_type}, "
                "which is not supported in a tool result: only images are, rasterize it to PNG"
            )
        return {
            "type": "image",
            "data": self._base64_data(),
            "mimeType": self.media_type,
        }

    def _base64_data(self) -> str:
        if self.data is None:
            raise ValueError(
                f"Attachment {self.key!r} has no data: hydrate it from the attachment store first"
            )
        return base64.standard_b64encode(self.data).decode("ascii")
