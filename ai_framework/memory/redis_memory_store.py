from typing import Any

import redis

from ai_framework.entities.message import Message


class RedisMemoryStore:
    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url)

    def _key(self, thread_id: str) -> str:
        return f"ai:messages:{thread_id}"

    def get_messages(self, thread_id: str) -> list[Message]:
        raw_messages: Any = self._client.lrange(self._key(thread_id), 0, -1)
        return [Message.model_validate_json(raw) for raw in raw_messages]

    def add_message(self, thread_id: str, message: Message) -> None:
        self._client.rpush(self._key(thread_id), message.model_dump_json())

    def clear(self, thread_id: str) -> None:
        self._client.delete(self._key(thread_id))
