from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest

boto3 = pytest.importorskip("boto3")

from ai_framework.attachments.s3_attachment_store import S3AttachmentStore  # noqa: E402

S3_URL = os.environ.get("AI_FRAMEWORK_TEST_S3_URL")
S3_ACCESS_KEY = os.environ.get("AI_FRAMEWORK_TEST_S3_ACCESS_KEY", "test")
S3_SECRET_KEY = os.environ.get("AI_FRAMEWORK_TEST_S3_SECRET_KEY", "testtest1")

pytestmark = pytest.mark.skipif(
    S3_URL is None,
    reason="AI_FRAMEWORK_TEST_S3_URL is not set",
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
    b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PREFIX = "attachments/test"


@pytest.fixture
def bucket() -> Iterator[str]:
    client = boto3.client(
        "s3",
        endpoint_url=S3_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )
    name = f"ai-framework-test-{uuid4().hex[:12]}"
    client.create_bucket(Bucket=name)
    yield name
    for item in client.list_objects_v2(Bucket=name).get("Contents", []):
        client.delete_object(Bucket=name, Key=item["Key"])
    client.delete_bucket(Bucket=name)


@pytest.fixture
def store(bucket: str) -> S3AttachmentStore:
    assert S3_URL is not None
    return S3AttachmentStore(
        endpoint_url=S3_URL,
        bucket=bucket,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        prefix=PREFIX,
    )


def _content_type(bucket: str, key: str) -> str:
    client = boto3.client(
        "s3",
        endpoint_url=S3_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )
    content_type: str = client.head_object(Bucket=bucket, Key=key)["ContentType"]
    return content_type


@pytest.mark.parametrize(
    ("data", "media_type", "extension"),
    [
        (PNG_BYTES, "image/png", ".png"),
        (PDF_BYTES, "application/pdf", ".pdf"),
    ],
    ids=["png", "pdf"],
)
def test_put_then_get_returns_same_bytes(
    store: S3AttachmentStore,
    bucket: str,
    data: bytes,
    media_type: str,
    extension: str,
):
    key = store.put(data, media_type)

    assert key.startswith(f"{PREFIX}/")
    assert key.endswith(extension)
    assert store.get(key) == data
    assert _content_type(bucket, key) == media_type


def test_put_gives_new_key_each_time(store: S3AttachmentStore):
    first = store.put(PNG_BYTES, "image/png")
    second = store.put(PNG_BYTES, "image/png")

    assert first != second
    assert store.get(first) == PNG_BYTES


def test_get_missing_key_raises_key_error(store: S3AttachmentStore):
    with pytest.raises(KeyError):
        store.get(f"{PREFIX}/missing.png")


def test_get_prefix_of_existing_key_raises_key_error(store: S3AttachmentStore):
    key = store.put(PDF_BYTES, "application/pdf")

    with pytest.raises(KeyError):
        store.get(key.removesuffix(".pdf"))
