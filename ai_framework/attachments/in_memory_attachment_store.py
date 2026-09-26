from __future__ import annotations

from uuid import uuid4

from ai_framework.entities.attachment import ATTACHMENT_FILE_EXTENSIONS


class InMemoryAttachmentStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put(self, data: bytes, media_type: str) -> str:
        key = f"{uuid4().hex}{ATTACHMENT_FILE_EXTENSIONS.get(media_type, '')}"
        self._objects[key] = data
        return key

    def get(self, key: str) -> bytes:
        return self._objects[key]
