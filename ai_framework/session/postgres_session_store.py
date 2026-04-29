import psycopg
from psycopg.rows import class_row

from ai_framework.entities.session import Session


class PostgresSessionStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_or_create(self, thread_id: str) -> Session:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=class_row(Session)) as cur:
                cur.execute(
                    """
                    INSERT INTO ai_sessions (thread_id)
                    VALUES (%(thread_id)s)
                    ON CONFLICT (thread_id) DO UPDATE SET thread_id = EXCLUDED.thread_id
                    RETURNING *
                    """,
                    {"thread_id": thread_id},
                )
                result = cur.fetchone()
                if result is None:
                    raise ValueError("Failed to create session")
                return result

    def get(self, thread_id: str) -> Session | None:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=class_row(Session)) as cur:
                cur.execute(
                    "SELECT * FROM ai_sessions WHERE thread_id = %(thread_id)s",
                    {"thread_id": thread_id},
                )
                return cur.fetchone()

    def update_language(self, thread_id: str, language: str) -> None:
        with psycopg.connect(self._database_url) as conn:
            conn.execute(
                "UPDATE ai_sessions SET language = %(language)s, updated_at = now() "
                "WHERE thread_id = %(thread_id)s",
                {"thread_id": thread_id, "language": language},
            )

    def touch(self, thread_id: str) -> None:
        with psycopg.connect(self._database_url) as conn:
            conn.execute(
                "UPDATE ai_sessions SET last_message_at = now(), updated_at = now() "
                "WHERE thread_id = %(thread_id)s",
                {"thread_id": thread_id},
            )
