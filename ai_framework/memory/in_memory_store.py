from ai_framework.entities.message import Message


class InMemoryStore:
    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}

    def get_messages(self, thread_id: str) -> list[Message]:
        return list(self._store.get(thread_id, []))

    def add_message(self, thread_id: str, message: Message) -> None:
        if thread_id not in self._store:
            self._store[thread_id] = []
        self._store[thread_id].append(message)

    def clear(self, thread_id: str) -> None:
        self._store.pop(thread_id, None)
