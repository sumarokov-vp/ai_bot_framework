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
        if self.data is None:
            raise ValueError(
                f"Attachment {self.key!r} has no data: hydrate it from the attachment store first"
            )
        block_type = "document" if self.media_type == "application/pdf" else "image"
        return {
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": self.media_type,
                "data": base64.standard_b64encode(self.data).decode("ascii"),
            },
        }
