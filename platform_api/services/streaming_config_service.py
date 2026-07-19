"""Backblaze B2 / CDN configuration for the music streaming platform."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

from platform_api.config import Settings, get_settings
from platform_api.services.billing_config_service import load_system_setting, mask_secret_value

logger = logging.getLogger(__name__)

STREAMING_B2_KEY_ID_KEY = "streaming.b2.key_id"
STREAMING_B2_APPLICATION_KEY_KEY = "streaming.b2.application_key"
STREAMING_B2_BUCKET_KEY = "streaming.b2.bucket"
STREAMING_B2_REGION_KEY = "streaming.b2.region"
STREAMING_B2_ENDPOINT_KEY = "streaming.b2.endpoint"
STREAMING_CDN_BASE_URL_KEY = "streaming.cdn_base_url"
STREAMING_URL_TTL_KEY = "streaming.stream_url_ttl_seconds"

SecretSource = Literal["database", "environment", "none"]


@dataclass(frozen=True, slots=True)
class StreamingStorageConfig:
    key_id: str
    application_key: str
    bucket: str
    region: str
    endpoint: str
    cdn_base_url: str
    stream_url_ttl_seconds: int
    secret_source: SecretSource
    configured: bool


@dataclass(frozen=True, slots=True)
class StreamingStorageConfigPublic:
    bucket: str
    region: str
    endpoint: str
    cdn_base_url: str
    stream_url_ttl_seconds: int
    key_id_masked: str
    application_key_masked: str
    secret_source: SecretSource
    configured: bool


async def _upsert_system_setting(pool: Any, *, key: str, value: str, value_type: str = "string") -> None:
    await pool.execute(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        key,
        value,
        value_type,
    )


def _encrypt_secret(plaintext: str, *, master_key: str | None = None) -> str:
    resolved_key = (
        str(master_key).strip()
        if master_key is not None
        else get_settings().encryption_master_key.strip()
    )
    if not resolved_key:
        return plaintext
    from platform_api.services.key_encryption import KeyEncryption

    encrypted = KeyEncryption(master_key=resolved_key).encrypt(plaintext)
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def _decrypt_secret(value: str, *, master_key: str | None = None) -> str:
    resolved_key = (
        str(master_key).strip()
        if master_key is not None
        else get_settings().encryption_master_key.strip()
    )
    if not resolved_key:
        logger.debug("No encryption master key set — returning raw value for streaming secret.")
        return value
    from platform_api.services.key_encryption import KeyEncryption

    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        decrypted = KeyEncryption(master_key=resolved_key).decrypt(raw)
        return decrypted
    except Exception as exc:
        logger.error(
            "Failed to decrypt streaming secret (length=%d). "
            "The ENCRYPTION_MASTER_KEY may have changed since this value was stored. "
            "Re-save the streaming config in admin Settings to fix. Error: %s",
            len(value),
            exc,
        )
        return value


async def resolve_streaming_storage_config(
    pool: Any,
    *,
    settings: Settings | None = None,
) -> StreamingStorageConfig:
    if settings is not None:
        resolved = settings
    else:
        try:
            resolved = get_settings()
        except Exception:
            from types import SimpleNamespace

            resolved = SimpleNamespace(
                encryption_master_key=os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", ""),
                streaming_b2_key_id=os.environ.get("PLATFORM_STREAMING_B2_KEY_ID", ""),
                streaming_b2_application_key=os.environ.get("PLATFORM_STREAMING_B2_APPLICATION_KEY", ""),
                streaming_b2_bucket=os.environ.get("PLATFORM_STREAMING_B2_BUCKET", "camxora-media"),
                streaming_b2_region=os.environ.get("PLATFORM_STREAMING_B2_REGION", "us-west-004"),
                streaming_b2_endpoint=os.environ.get("PLATFORM_STREAMING_B2_ENDPOINT", ""),
                streaming_cdn_base_url=os.environ.get("PLATFORM_STREAMING_CDN_BASE_URL", ""),
                streaming_stream_url_ttl_seconds=int(
                    os.environ.get("PLATFORM_STREAMING_STREAM_URL_TTL_SECONDS", "3600") or 3600
                ),
            )
    master_key = resolved.encryption_master_key.strip() or os.environ.get(
        "PLATFORM_ENCRYPTION_MASTER_KEY", ""
    ).strip()

    db_key_id = await load_system_setting(pool, STREAMING_B2_KEY_ID_KEY)
    db_app_key = await load_system_setting(pool, STREAMING_B2_APPLICATION_KEY_KEY)
    db_bucket = await load_system_setting(pool, STREAMING_B2_BUCKET_KEY)
    db_region = await load_system_setting(pool, STREAMING_B2_REGION_KEY)
    db_endpoint = await load_system_setting(pool, STREAMING_B2_ENDPOINT_KEY)
    db_cdn = await load_system_setting(pool, STREAMING_CDN_BASE_URL_KEY)
    db_ttl = await load_system_setting(pool, STREAMING_URL_TTL_KEY)

    secret_source: SecretSource = "none"
    application_key = ""
    if db_app_key:
        application_key = _decrypt_secret(db_app_key, master_key=master_key)
        secret_source = "database"
    elif resolved.streaming_b2_application_key.strip():
        application_key = resolved.streaming_b2_application_key.strip()
        secret_source = "environment"

    key_id = (db_key_id or resolved.streaming_b2_key_id or "").strip()
    bucket = (db_bucket or resolved.streaming_b2_bucket or "camxora-media").strip()
    region = (db_region or resolved.streaming_b2_region or "us-west-004").strip()
    endpoint = (db_endpoint or resolved.streaming_b2_endpoint or "").strip()
    if not endpoint:
        endpoint = f"https://s3.{region}.backblazeb2.com"
    cdn_base_url = (db_cdn or resolved.streaming_cdn_base_url or "").strip().rstrip("/")
    ttl_raw = (db_ttl or str(resolved.streaming_stream_url_ttl_seconds)).strip()
    try:
        stream_url_ttl_seconds = max(300, int(ttl_raw))
    except ValueError:
        stream_url_ttl_seconds = resolved.streaming_stream_url_ttl_seconds

    configured = bool(key_id and application_key and bucket and endpoint)
    return StreamingStorageConfig(
        key_id=key_id,
        application_key=application_key,
        bucket=bucket,
        region=region,
        endpoint=endpoint.rstrip("/"),
        cdn_base_url=cdn_base_url,
        stream_url_ttl_seconds=stream_url_ttl_seconds,
        secret_source=secret_source,
        configured=configured,
    )


async def get_streaming_storage_config_public(pool: Any) -> StreamingStorageConfigPublic:
    config = await resolve_streaming_storage_config(pool)
    return StreamingStorageConfigPublic(
        bucket=config.bucket,
        region=config.region,
        endpoint=config.endpoint,
        cdn_base_url=config.cdn_base_url,
        stream_url_ttl_seconds=config.stream_url_ttl_seconds,
        key_id_masked=mask_secret_value(config.key_id),
        application_key_masked=mask_secret_value(config.application_key),
        secret_source=config.secret_source,
        configured=config.configured,
    )


async def save_streaming_storage_config(
    pool: Any,
    *,
    key_id: str,
    application_key: str,
    bucket: str,
    region: str,
    endpoint: str,
    cdn_base_url: str,
    stream_url_ttl_seconds: int,
) -> StreamingStorageConfigPublic:
    stored_app_key = (
        _encrypt_secret(application_key.strip(), master_key=get_settings().encryption_master_key)
        if application_key.strip()
        else ""
    )
    await _upsert_system_setting(pool, key=STREAMING_B2_KEY_ID_KEY, value=key_id.strip())
    if stored_app_key:
        await _upsert_system_setting(
            pool,
            key=STREAMING_B2_APPLICATION_KEY_KEY,
            value=stored_app_key,
            value_type="encrypted_string" if get_settings().encryption_master_key.strip() else "string",
        )
    await _upsert_system_setting(pool, key=STREAMING_B2_BUCKET_KEY, value=bucket.strip())
    await _upsert_system_setting(pool, key=STREAMING_B2_REGION_KEY, value=region.strip())
    await _upsert_system_setting(pool, key=STREAMING_B2_ENDPOINT_KEY, value=endpoint.strip())
    await _upsert_system_setting(pool, key=STREAMING_CDN_BASE_URL_KEY, value=cdn_base_url.strip().rstrip("/"))
    await _upsert_system_setting(
        pool,
        key=STREAMING_URL_TTL_KEY,
        value=str(max(300, int(stream_url_ttl_seconds))),
    )
    return await get_streaming_storage_config_public(pool)
