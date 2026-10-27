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

    async def probe(self) -> None:
        """Verify the stored credential can actually reach the bucket.

        Readiness used to treat "bucket and keys present" as healthy, so a
        truncated or wrong-scoped key still reported ``storage: true`` while
        every upload failed. This performs a real authenticated call with short
        timeouts, and raises on failure so the caller can mark readiness down.
        """

        def _head() -> None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=self._config.endpoint,
                aws_access_key_id=self._config.key_id,
                aws_secret_access_key=self._config.application_key,
                region_name=self._config.region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    connect_timeout=5,
                    read_timeout=5,
                    retries={"max_attempts": 1},
                ),
            )
            client.head_bucket(Bucket=self._config.bucket)

        await asyncio.to_thread(_head)

    async def get_signed_get_url(self, key: str, *, cache_bust: bool = False) -> str:
        normalized_key = key.lstrip("/")
        if self._config.cdn_base_url:
            base = self._config.cdn_base_url.rstrip("/")
            url = f"{base}/{quote(normalized_key, safe='/')}"
            if cache_bust:
                # The CDN caches by URL for a long TTL, so an overwritten object
                # keeps serving the old bytes until purge. Appending the current
                # object version (ETag) makes the CDN fetch fresh content.
                version = await self._object_version(normalized_key)
                if version:
                    url = f"{url}?v={quote(version, safe='')}"
            return url

        def _sign() -> str:
            client = self._client()
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._config.bucket, "Key": normalized_key},
                ExpiresIn=self._config.stream_url_ttl_seconds,
            )

        return await asyncio.to_thread(_sign)

    async def _object_version(self, key: str) -> str:
        """Current object ETag (content hash) for CDN cache-busting; '' on failure."""

        def _head() -> str:
            client = self._client()
            response = client.head_object(Bucket=self._config.bucket, Key=key)
            etag = str(response.get("ETag") or "").strip().strip('"')
            if etag:
                return etag
            last_modified = response.get("LastModified")
            return last_modified.isoformat() if last_modified else ""

        try:
            return await asyncio.to_thread(_head)
        except Exception:
            logger.warning("CDN cache-bust HEAD failed for %s", key, exc_info=True)
            return ""

    async def download_bytes(self, key: str) -> bytes:
        """Fetch an object's raw bytes directly (server-side read-back).

        Used for server-side fallback reads (e.g. image job output serving) where
        the API itself needs the bytes, as opposed to `get_signed_get_url()` which
        hands the client a URL to fetch from directly.
        """
        normalized_key = key.lstrip("/")

        def _get() -> bytes:
            client = self._client()
            response = client.get_object(Bucket=self._config.bucket, Key=normalized_key)
            return response["Body"].read()

        return await asyncio.to_thread(_get)
