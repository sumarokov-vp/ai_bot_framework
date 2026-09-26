from __future__ import annotations

import logging
import os
import struct
import uuid
import zlib
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

boto3 = pytest.importorskip("boto3")
pytest.importorskip("claude_agent_sdk")

from ai_framework import AIApplication, Attachment, Provider  # noqa: E402
from ai_framework.attachments.s3_attachment_store import S3AttachmentStore  # noqa: E402

logger = logging.getLogger(__name__)

ADMIN_DATABASE_URL = os.environ.get("AI_FRAMEWORK_TEST_DATABASE_URL")
S3_URL = os.environ.get("AI_FRAMEWORK_TEST_S3_URL")
S3_ACCESS_KEY = os.environ.get("AI_FRAMEWORK_TEST_S3_ACCESS_KEY", "test")
S3_SECRET_KEY = os.environ.get("AI_FRAMEWORK_TEST_S3_SECRET_KEY", "testtest1")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

MODEL = "claude-haiku-4-5"
SYSTEM_PROMPT = "You are a terse assistant. Answer in one short line."
IMAGE_WORD = "MANGO"
PDF_PHRASE = "purple elephants dance at noon"
EXACT = "Ответь дословно, теми же латинскими буквами, без перевода и транслитерации."
IMAGE_QUESTION = f"Какое слово написано на картинке? {EXACT}"
PDF_QUESTION = f"Что написано в документе? {EXACT}"
RECALL_QUESTION = f"Какое слово было написано на картинке? {EXACT}"

pytestmark = pytest.mark.skipif(
    ADMIN_DATABASE_URL is None or S3_URL is None,
    reason="AI_FRAMEWORK_TEST_DATABASE_URL and AI_FRAMEWORK_TEST_S3_URL are required",
)

GLYPHS: dict[str, tuple[str, ...]] = {
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def render_word_png(word: str, scale: int = 16, margin: int = 2) -> bytes:
    cells = [""] * 7
    for index, letter in enumerate(word):
        for line_number in range(7):
            cells[line_number] += ("0" if index else "") + GLYPHS[letter][line_number]
    padded = (
        ["0" * (len(cells[0]) + 2 * margin)] * margin
        + ["0" * margin + row + "0" * margin for row in cells]
        + ["0" * (len(cells[0]) + 2 * margin)] * margin
    )
    raw = b""
    for pixels in padded:
        line = b"".join(
            (b"\x00" if cell == "1" else b"\xff") * scale for cell in pixels
        )
        raw += (b"\x00" + line) * scale
    width = len(padded[0]) * scale
    height = len(padded) * scale
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def render_phrase_pdf(phrase: str) -> bytes:
    stream = f"BT /F1 28 Tf 72 700 Td ({phrase}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    document = b"%PDF-1.4\n"
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        document += f"{offset:010d} 00000 n \n".encode()
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return document


class CountingS3AttachmentStore:
    def __init__(self, inner: S3AttachmentStore) -> None:
        self._inner = inner
        self.get_calls = 0

    def put(self, data: bytes, media_type: str) -> str:
        return self._inner.put(data, media_type)

    def get(self, key: str) -> bytes:
        self.get_calls += 1
        return self._inner.get(key)


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


@pytest.fixture
def bucket() -> Iterator[str]:
    client = boto3.client(
        "s3",
        endpoint_url=S3_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )
    name = f"ai-framework-live-{uuid.uuid4().hex[:12]}"
    client.create_bucket(Bucket=name)
    yield name
    for item in client.list_objects_v2(Bucket=name).get("Contents", []):
        client.delete_object(Bucket=name, Key=item["Key"])
    client.delete_bucket(Bucket=name)


def _s3_store(bucket: str) -> CountingS3AttachmentStore:
    assert S3_URL is not None
    return CountingS3AttachmentStore(
        S3AttachmentStore(
            endpoint_url=S3_URL,
            bucket=bucket,
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            prefix="live",
        )
    )


def _stored_attachments(database_url: str, thread_id: str) -> list[dict[str, object]]:
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(
            "SELECT attachments FROM ai_messages "
            "WHERE thread_id = %s AND attachments IS NOT NULL ORDER BY id",
            (thread_id,),
        ).fetchall()
    return [item for (items,) in rows for item in items]


def _assert_only_references(database_url: str, thread_id: str, count: int) -> None:
    stored = _stored_attachments(database_url, thread_id)
    logger.info("ai_messages.attachments: %s", stored)
    assert len(stored) == count
    for item in stored:
        assert set(item) == {"key", "media_type", "filename"}
        assert str(item["key"]).startswith("live/")


def test_claude_sdk_reads_image_and_pdf_across_restart(
    database_url: str, bucket: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    thread_id = f"live-sdk-{uuid.uuid4().hex[:8]}"

    first_store = _s3_store(bucket)
    with AIApplication(
        api_key="",
        system_prompt=SYSTEM_PROMPT,
        database_url=database_url,
        tools=[],
        model=MODEL,
        provider=Provider.CLAUDE_SDK,
        attachment_store=first_store,
    ) as app:
        image_answer = app.process_message(
            thread_id,
            IMAGE_QUESTION,
            attachments=[
                Attachment(
                    media_type="image/png",
                    filename="word.png",
                    data=render_word_png(IMAGE_WORD),
                )
            ],
        )
        logger.info("ход 1 (PNG): %r", image_answer.content)
        assert IMAGE_WORD.lower() in (image_answer.content or "").lower()

        pdf_answer = app.process_message(
            thread_id,
            PDF_QUESTION,
            attachments=[
                Attachment(
                    media_type="application/pdf",
                    filename="phrase.pdf",
                    data=render_phrase_pdf(PDF_PHRASE),
                )
            ],
        )
        logger.info("ход 2 (PDF): %r", pdf_answer.content)
        assert PDF_PHRASE in (pdf_answer.content or "").lower()
    assert first_store.get_calls == 0

    restarted_store = _s3_store(bucket)
    with AIApplication(
        api_key="",
        system_prompt=SYSTEM_PROMPT,
        database_url=database_url,
        tools=[],
        model=MODEL,
        provider=Provider.CLAUDE_SDK,
        attachment_store=restarted_store,
    ) as restarted:
        recall_answer = restarted.process_message(
            thread_id,
            RECALL_QUESTION,
        )
    logger.info("ход 3 (после перезапуска): %r", recall_answer.content)
    logger.info("чтений из S3 на ходе 3: %s", restarted_store.get_calls)
    assert IMAGE_WORD.lower() in (recall_answer.content or "").lower()
    assert restarted_store.get_calls == 2

    _assert_only_references(database_url, thread_id, count=2)


@pytest.mark.skipif(ANTHROPIC_API_KEY is None, reason="ANTHROPIC_API_KEY is not set")
def test_anthropic_reads_image(database_url: str, bucket: str) -> None:
    assert ANTHROPIC_API_KEY is not None
    thread_id = f"live-api-{uuid.uuid4().hex[:8]}"
    with AIApplication(
        api_key=ANTHROPIC_API_KEY,
        system_prompt=SYSTEM_PROMPT,
        database_url=database_url,
        tools=[],
        model=MODEL,
        provider=Provider.ANTHROPIC,
        attachment_store=_s3_store(bucket),
    ) as app:
        answer = app.process_message(
            thread_id,
            IMAGE_QUESTION,
            attachments=[
                Attachment(
                    media_type="image/png",
                    filename="word.png",
                    data=render_word_png(IMAGE_WORD),
                )
            ],
        )
    logger.info("AnthropicProvider (PNG): %r", answer.content)
    assert IMAGE_WORD.lower() in (answer.content or "").lower()
    _assert_only_references(database_url, thread_id, count=1)
