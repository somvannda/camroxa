"""S3-compatible object storage (Backblaze B2) for music streaming."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from platform_api.services.streaming_config_service import StreamingStorageConfig

logger = logging.getLogger(__name__)


class StorageServiceError(RuntimeError):
    pass


class StorageService:
    """Upload objects and mint signed playback URLs against B2."""

    def __init__(self, config: StreamingStorageConfig) -> None:
        if not config.configured:
            raise StorageServiceError("Streaming storage is not configured.")
        self._config = config

    @staticmethod
    def from_config(config: StreamingStorageConfig) -> StorageService:
        return StorageService(config)

    def _client(self) -> Any:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=self._config.endpoint,
            aws_access_key_id=self._config.key_id,
            aws_secret_access_key=self._config.application_key,
            region_name=self._config.region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def upload_bytes(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        normalized_key = key.lstrip("/")

        def _put() -> None:
            client = self._client()
            client.put_object(
                Bucket=self._config.bucket,
                Key=normalized_key,
                Body=data,
                ContentType=content_type,
            )

        await asyncio.to_thread(_put)
        return normalized_key

    async def get_signed_get_url(self, key: str) -> str:
        normalized_key = key.lstrip("/")
        if self._config.cdn_base_url:
            base = self._config.cdn_base_url.rstrip("/")
            return f"{base}/{quote(normalized_key, safe='/')}"

        def _sign() -> str:
            client = self._client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": normalized_key},
                ExpiresIn=self._config.stream_url_ttl_seconds,
            )

        return await asyncio.to_thread(_sign)
