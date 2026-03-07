import json
from typing import Any

import psycopg

from ai_framework.entities.message import Message
from ai_framework.entities.tool import ToolCall, ToolResult


class PostgresMemoryStore:
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

    def get_messages(self, thread_id: str) -> list[Message]:
        cursor = self._connection.execute(
            "SELECT role, content, tool_calls, tool_results "
            "FROM ai_messages WHERE thread_id = %s ORDER BY id",
            (thread_id,),
        )
        messages: list[Message] = []
        rows: list[Any] = cursor.fetchall()
        for role, content, tool_calls_json, tool_results_json in rows:
            tool_calls = (
                [ToolCall(**tc) for tc in tool_calls_json]
                if tool_calls_json
                else None
            )
            tool_results = (
                [ToolResult(**tr) for tr in tool_results_json]
                if tool_results_json
                else None
            )
            messages.append(
                Message(
                    role=role,
                    content=str(content),
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                )
            )
        return messages

    def add_message(self, thread_id: str, message: Message) -> None:
        tool_calls_json = (
            json.dumps([tc.model_dump() for tc in message.tool_calls])
            if message.tool_calls
            else None
        )
        tool_results_json = (
            json.dumps([tr.model_dump() for tr in message.tool_results])
            if message.tool_results
            else None
        )
        self._connection.execute(
            "INSERT INTO ai_messages (thread_id, role, content, tool_calls, tool_results) "
            "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)",
            (thread_id, message.role, message.content, tool_calls_json, tool_results_json),
        )
        self._connection.commit()

    def clear(self, thread_id: str) -> None:
        self._connection.execute(
            "DELETE FROM ai_messages WHERE thread_id = %s",
            (thread_id,),
        )
        self._connection.commit()
