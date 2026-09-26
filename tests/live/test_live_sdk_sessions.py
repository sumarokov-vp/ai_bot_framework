from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

pytest.importorskip("claude_agent_sdk")

from ai_framework import AIApplication, Provider  # noqa: E402

logger = logging.getLogger(__name__)

ADMIN_DATABASE_URL = os.environ.get("AI_FRAMEWORK_TEST_DATABASE_URL")

MODEL = "claude-haiku-4-5"
SYSTEM_PROMPT = "You are a terse assistant. Answer in one short line."
CODE_WORD = "PAPAYA"
TELL = f"Запомни кодовое слово: {CODE_WORD}. Ответь одним словом: запомнил."
RECALL = (
    "Какое кодовое слово я тебе называл в этом разговоре? "
    "Если я ничего не называл — ответь ровно NONE."
)

pytestmark = pytest.mark.skipif(
    ADMIN_DATABASE_URL is None,
    reason="AI_FRAMEWORK_TEST_DATABASE_URL is required",
)


@pytest.fixture
def database_url() -> Iterator[str]:
    assert ADMIN_DATABASE_URL is not None
    name = f"ai_framework_live_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    yield urlunsplit(urlsplit(ADMIN_DATABASE_URL)._replace(path=f"/{name}"))
    with psycopg.connect(ADMIN_DATABASE_URL, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )


def _ask(app: AIApplication, thread_id: str, text: str) -> str:
    answer = app.process_message(thread_id, text).content or ""
    logger.info("[%s] %s -> %s", thread_id, text, answer)
    return answer


def test_claude_sdk_session_is_per_thread_and_cleared_with_context(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    thread_a = f"live-a-{uuid.uuid4().hex[:8]}"
    thread_b = f"live-b-{uuid.uuid4().hex[:8]}"

    with AIApplication(
        api_key="",
        system_prompt=SYSTEM_PROMPT,
        database_url=database_url,
        tools=[],
        model=MODEL,
        provider=Provider.CLAUDE_SDK,
    ) as app:
        _ask(app, thread_a, TELL)
        assert CODE_WORD in _ask(app, thread_a, RECALL).upper()
        assert CODE_WORD not in _ask(app, thread_b, RECALL).upper()

        app.clear_context(thread_a)

        assert CODE_WORD not in _ask(app, thread_a, RECALL).upper()
