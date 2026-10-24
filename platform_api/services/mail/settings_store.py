"""Mail credentials stored in the database, encrypted at rest.

Values live in ``system_settings`` so an operator can rotate a key from the admin
portal without a redeploy — the failure mode we hit with env, where a generated
``.env`` silently dropped anything not in its fixed list.

Secrets are encrypted with Fernet, keyed from PLATFORM_JWT_SECRET plus a domain
prefix, so a ciphertext from here cannot be replayed elsewhere. The decrypted
values are written into the cached Settings object, which the mailer and worker
already read, so nothing downstream needs to know this table exists.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from platform_api.config import get_settings

KEY_API = "mail.resend_api_key"
KEY_WEBHOOK = "mail.resend_webhook_secret"
KEY_FROM_TX = "mail.from_transactional"
KEY_FROM_CAMPAIGN = "mail.from_campaign"
KEY_BASE_URL = "mail.public_base_url"
KEY_APP_URL = "mail.app_url"

SECRET_KEYS = (KEY_API, KEY_WEBHOOK)

# Process-local flag: the worker calls ensure_loaded before every batch, so a
# restart picks the stored credentials up on the first tick.
_loaded = False


def _fernet() -> Fernet:
    settings = get_settings()
    secret = getattr(settings, "jwt_secret", "") or getattr(settings, "secret_key", "")
    if not secret:
        raise RuntimeError("PLATFORM_JWT_SECRET is required to encrypt mail credentials.")
    digest = hashlib.sha256(f"camxora-mail:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Key rotated or value written by another deployment: treat as unset
        # rather than crashing a mail tick.
        return ""


async def _read(pool: Any) -> dict[str, str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value_type, value FROM system_settings WHERE key = ANY($1::text[])",
            [KEY_API, KEY_WEBHOOK, KEY_FROM_TX, KEY_FROM_CAMPAIGN, KEY_BASE_URL, KEY_APP_URL],
        )
    out: dict[str, str] = {}
    for row in rows:
        value = row["value"] or ""
        out[row["key"]] = decrypt(value) if row["value_type"] == "encrypted" else value
    return out


def _apply(values: dict[str, str]) -> None:
    settings = get_settings()
    if values.get(KEY_API):
        settings.resend_api_key = values[KEY_API]
    if values.get(KEY_WEBHOOK):
        settings.resend_webhook_secret = values[KEY_WEBHOOK]
    if values.get(KEY_FROM_TX):
        settings.mail_from_transactional = values[KEY_FROM_TX]
    if values.get(KEY_FROM_CAMPAIGN):
        settings.mail_from_campaign = values[KEY_FROM_CAMPAIGN]
    if values.get(KEY_BASE_URL):
        settings.mail_public_base_url = values[KEY_BASE_URL]
    if values.get(KEY_APP_URL):
        settings.mail_app_url = values[KEY_APP_URL]


async def ensure_loaded(pool: Any) -> None:
    """Load stored credentials into Settings once per process."""
    global _loaded
    if _loaded:
        return
    try:
        _apply(await _read(pool))
    finally:
        # Even on failure, do not hammer the table on every tick.
        _loaded = True


async def public_view(pool: Any) -> dict[str, Any]:
    """UI-safe view: secrets are reported as configured, never returned."""
    values = await _read(pool)
    settings = get_settings()
    return {
        "configured": bool(values.get(KEY_API) or settings.resend_api_key),
        "webhook_configured": bool(values.get(KEY_WEBHOOK) or settings.resend_webhook_secret),
        "from_transactional": values.get(KEY_FROM_TX) or settings.mail_from_transactional,
        "from_campaign": values.get(KEY_FROM_CAMPAIGN) or settings.mail_from_campaign,
        "public_base_url": values.get(KEY_BASE_URL) or settings.mail_public_base_url,
        "app_url": values.get(KEY_APP_URL) or settings.mail_app_url,
        "enabled": settings.mail_enabled,
    }


async def save(pool: Any, patch: dict[str, Any]) -> None:
    """Upsert the provided fields. An empty string clears a value."""
    mapping = {
        KEY_API: ("apiKey", "encrypted"),
        KEY_WEBHOOK: ("webhookSecret", "encrypted"),
        KEY_FROM_TX: ("fromTransactional", "string"),
        KEY_FROM_CAMPAIGN: ("fromCampaign", "string"),
        KEY_BASE_URL: ("publicBaseUrl", "string"),
        KEY_APP_URL: ("appUrl", "string"),
    }

    async with pool.acquire() as conn:
        for key, (field, value_type) in mapping.items():
            if field not in patch:
                continue
            raw = patch.get(field)
            value = "" if raw is None else str(raw).strip()

            if value == "":
                await conn.execute("DELETE FROM system_settings WHERE key = $1", key)
                continue

            stored = encrypt(value) if value_type == "encrypted" else value
            await conn.execute(
                """
                INSERT INTO system_settings (key, value_type, value, updated_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value,
                      value_type = EXCLUDED.value_type,
                      updated_at = now()
                """,
                key,
                value_type,
                stored,
            )

    _apply(await _read(pool))


def reset_cache() -> None:
    """Test helper: forget that settings were loaded."""
    global _loaded
    _loaded = False
