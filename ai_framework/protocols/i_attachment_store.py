from __future__ import annotations

from typing import Protocol


class IAttachmentStore(Protocol):
    def put(self, data: bytes, media_type: str) -> str: ...

    def get(self, key: str) -> bytes: ...
