from __future__ import annotations

from ai_framework.memory.postgres_memory_store import PostgresMemoryStore
from ai_framework.migrations import apply_migrations
from ai_framework.protocols.i_memory_store import IMemoryStore
from ai_framework.protocols.i_session_store import ISessionStore
from ai_framework.session.postgres_session_store import PostgresSessionStore


class InfrastructureContext:
    def __init__(self, memory: IMemoryStore, sessions: ISessionStore) -> None:
        self.memory = memory
        self.sessions = sessions

    def close(self) -> None:
        self.sessions.close()
        self.memory.close()


def open_infrastructure(database_url: str) -> InfrastructureContext:
    apply_migrations(database_url)
    return InfrastructureContext(
        memory=PostgresMemoryStore(database_url),
        sessions=PostgresSessionStore(database_url),
    )
