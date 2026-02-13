from __future__ import annotations

from typing import Protocol

from ai_framework.entities.message import Message


class IMemoryStore(Protocol):
    def get_messages(self, thread_id: str) -> list[Message]: ...

    def add_message(self, thread_id: str, message: Message) -> None: ...

    def clear(self, thread_id: str) -> None: ...
