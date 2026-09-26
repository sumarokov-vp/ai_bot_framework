from __future__ import annotations

from uuid import uuid4

import boto3

from ai_framework.entities.attachment import ATTACHMENT_FILE_EXTENSIONS


class S3AttachmentStore:
    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        prefix: str = "",
    ) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def put(self, data: bytes, media_type: str) -> str:
        key = self._new_key(media_type)
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=media_type,
        )
        return key

    def get(self, key: str) -> bytes:
        if not self._exists(key):
            raise KeyError(key)
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    def _new_key(self, media_type: str) -> str:
        name = f"{uuid4().hex}{ATTACHMENT_FILE_EXTENSIONS.get(media_type, '')}"
        if not self._prefix:
            return name
        return f"{self._prefix}/{name}"

    def _exists(self, key: str) -> bool:
        listing = self._client.list_objects_v2(
            Bucket=self._bucket,
            Prefix=key,
            MaxKeys=1,
        )
        return any(item["Key"] == key for item in listing.get("Contents", []))
