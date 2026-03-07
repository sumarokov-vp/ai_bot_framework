from datetime import UTC, datetime
from typing import Any

import redis

from ai_framework.entities.session import Session


class RedisSessionStore:
    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url)

    def _key(self, thread_id: str) -> str:
        return f"ai:session:{thread_id}"

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
        self._client.set(self._key(thread_id), session.model_dump_json())
        return session

    def get(self, thread_id: str) -> Session | None:
        raw: Any = self._client.get(self._key(thread_id))
        if raw is None:
            return None
        return Session.model_validate_json(raw)

    def update_language(self, thread_id: str, language: str) -> None:
        session = self.get(thread_id)
        if not session:
            return
        updated = session.model_copy(
            update={"language": language, "updated_at": datetime.now(tz=UTC)},
        )
        self._client.set(self._key(thread_id), updated.model_dump_json())

    def touch(self, thread_id: str) -> None:
        session = self.get(thread_id)
        if not session:
            return
        now = datetime.now(tz=UTC)
        updated = session.model_copy(
            update={"last_message_at": now, "updated_at": now},
        )
        self._client.set(self._key(thread_id), updated.model_dump_json())
