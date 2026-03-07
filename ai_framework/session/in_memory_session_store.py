from datetime import UTC, datetime

from ai_framework.entities.session import Session


class InMemorySessionStore:
    def __init__(self) -> None:
        self._store: dict[str, Session] = {}

    def get_or_create(self, thread_id: str) -> Session:
        existing = self.get(thread_id)
        if existing:
            return existing
        now = datetime.now(tz=UTC)
        session = Session(
            thread_id=thread_id,
            created_at=now,
            updated_at=now,
        )
        self._store[thread_id] = session
        return session

    def get(self, thread_id: str) -> Session | None:
        return self._store.get(thread_id)

    def update_language(self, thread_id: str, language: str) -> None:
        session = self._store.get(thread_id)
        if not session:
            return
        self._store[thread_id] = session.model_copy(
            update={"language": language, "updated_at": datetime.now(tz=UTC)},
        )

    def touch(self, thread_id: str) -> None:
        session = self._store.get(thread_id)
        if not session:
            return
        now = datetime.now(tz=UTC)
        self._store[thread_id] = session.model_copy(
            update={"last_message_at": now, "updated_at": now},
        )
