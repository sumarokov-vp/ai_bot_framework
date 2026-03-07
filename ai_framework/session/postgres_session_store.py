from typing import Any

import psycopg
from psycopg.rows import class_row

from ai_framework.entities.session import Session


class PostgresSessionStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._conn: psycopg.Connection[Any] | None = None

    def open(self) -> None:
        self._conn = psycopg.connect(self._database_url)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def _connection(self) -> psycopg.Connection[Any]:
        if not self._conn:
            raise RuntimeError("Connection is not open. Call open() first.")
        return self._conn

    def get_or_create(self, thread_id: str) -> Session:
        existing = self.get(thread_id)
        if existing:
            return existing
        with self._connection.cursor(row_factory=class_row(Session)) as cur:
            cur.execute(
                """
                INSERT INTO ai_sessions (thread_id)
                VALUES (%(thread_id)s)
                ON CONFLICT (thread_id) DO UPDATE SET thread_id = EXCLUDED.thread_id
                RETURNING *
                """,
                {"thread_id": thread_id},
            )
            self._connection.commit()
            result = cur.fetchone()
            if result is None:
                raise ValueError("Failed to create session")
            return result

    def get(self, thread_id: str) -> Session | None:
        with self._connection.cursor(row_factory=class_row(Session)) as cur:
            cur.execute(
                "SELECT * FROM ai_sessions WHERE thread_id = %(thread_id)s",
                {"thread_id": thread_id},
            )
            return cur.fetchone()

    def update_language(self, thread_id: str, language: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                "UPDATE ai_sessions SET language = %(language)s, updated_at = now() "
                "WHERE thread_id = %(thread_id)s",
                {"thread_id": thread_id, "language": language},
            )
            self._connection.commit()

    def touch(self, thread_id: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(
                "UPDATE ai_sessions SET last_message_at = now(), updated_at = now() "
                "WHERE thread_id = %(thread_id)s",
                {"thread_id": thread_id},
            )
            self._connection.commit()
