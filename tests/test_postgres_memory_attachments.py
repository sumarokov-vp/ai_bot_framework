import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg import sql
import pytest
from yoyo import get_backend, read_migrations
from yoyo.backends.base import DatabaseBackend

import ai_framework.migrations

from ai_framework.entities.attachment import Attachment
from ai_framework.entities.message import Message
from ai_framework.memory.postgres_memory_store import PostgresMemoryStore
from ai_framework.migrations import apply_migrations


ADMIN_DATABASE_URL = os.environ.get("AI_FRAMEWORK_TEST_DATABASE_URL")
MIGRATIONS_DIR = Path(ai_framework.migrations.__file__).parent / "sql"

pytestmark = pytest.mark.skipif(
    ADMIN_DATABASE_URL is None,
    reason="AI_FRAMEWORK_TEST_DATABASE_URL is not set",
)


@pytest.fixture
def database_url() -> Iterator[str]:
    assert ADMIN_DATABASE_URL is not None
    name = f"ai_framework_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    yield urlunsplit(urlsplit(ADMIN_DATABASE_URL)._replace(path=f"/{name}"))
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )


def _attachments_column_exists(database_url: str) -> bool:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'ai_messages' AND column_name = 'attachments'"
        ).fetchone()
    return row is not None


def _yoyo_backend(database_url: str) -> DatabaseBackend:
    scheme, rest = database_url.split("://", 1)
    return get_backend(
        f"postgresql+psycopg://{rest}"
        if scheme.startswith("postgres")
        else database_url
    )


def test_apply_migrations_on_empty_database(database_url: str) -> None:
    assert apply_migrations(database_url) == 2
    assert _attachments_column_exists(database_url)


def test_apply_migrations_on_database_with_initial_schema(database_url: str) -> None:
    backend = _yoyo_backend(database_url)
    initial = read_migrations(str(MIGRATIONS_DIR)).filter(
        lambda m: m.id == "0001.ai-initial-schema"
    )
    with backend.lock():
        backend.apply_migrations(backend.to_apply(initial))
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO ai_messages (thread_id, role, content) VALUES ('old', 'user', 'hi')"
        )
    assert not _attachments_column_exists(database_url)

    assert apply_migrations(database_url) == 1

    messages = PostgresMemoryStore(database_url).get_messages("old")
    assert [(m.content, m.attachments) for m in messages] == [("hi", None)]


def test_attachments_round_trip_without_bytes(database_url: str) -> None:
    apply_migrations(database_url)
    store = PostgresMemoryStore(database_url)
    png = Attachment(
        media_type="image/png", filename="scan.png", key="t/1.png", data=b"\x89PNG"
    )
    pdf = Attachment(
        media_type="application/pdf", filename=None, key="t/2.pdf", data=b"%PDF-1.7"
    )

    store.add_message("t", Message(role="user", content="look", attachments=[png, pdf]))
    store.add_message("t", Message(role="assistant", content="ok"))

    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT attachments FROM ai_messages WHERE thread_id = 't' ORDER BY id LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row[0] == [
        {"key": "t/1.png", "media_type": "image/png", "filename": "scan.png"},
        {"key": "t/2.pdf", "media_type": "application/pdf", "filename": None},
    ]

    user_message, assistant_message = store.get_messages("t")
    assert user_message.attachments is not None
    assert [
        (a.key, a.media_type, a.filename, a.data) for a in user_message.attachments
    ] == [
        ("t/1.png", "image/png", "scan.png", None),
        ("t/2.pdf", "application/pdf", None, None),
    ]
    assert assistant_message.attachments is None


def test_rollback_of_attachments_migration(database_url: str) -> None:
    apply_migrations(database_url)
    backend = _yoyo_backend(database_url)
    attachments_migration = read_migrations(str(MIGRATIONS_DIR)).filter(
        lambda m: m.id == "0002.ai-message-attachments"
    )
    with backend.lock():
        backend.rollback_migrations(backend.to_rollback(attachments_migration))

    assert not _attachments_column_exists(database_url)
    assert apply_migrations(database_url) == 1
    assert _attachments_column_exists(database_url)
