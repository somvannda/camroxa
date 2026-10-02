"""Email-domain guard for music-web signups (production hotfix source).

Rejects disposable/temp-mail domains outright and caps the number of free
music-web accounts per non-trusted domain, so signup farms cannot keep burning
the free monthly pool with throwaway inboxes.

Lists + cap are read from system_settings (admin-editable, no redeploy):
  - signup_blocked_email_domains          json array of domains to reject
  - signup_trusted_email_domains          json array of domains exempt from cap
  - signup_max_free_accounts_per_domain   int  (default 3)

Rules:
  1. Only music_web product signups are guarded (studio is invite-gated).
  2. Trusted consumer domains (gmail etc.) are always allowed, no cap.
  3. Blocked domains are rejected with a clear 422.
  4. Any other domain may host at most N free music-web accounts; paid users
     (active license) are exempt and never count toward N.

Raised errors use ValidationError with the same shape auth.register() uses.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

logger = logging.getLogger("platform_api.services.signup_domain_guard")

MUSIC_WEB_PRODUCT = "music_web"

_SETTINGS_KEY_BLOCKED = "signup_blocked_email_domains"
_SETTINGS_KEY_TRUSTED = "signup_trusted_email_domains"
_SETTINGS_KEY_MAX = "signup_max_free_accounts_per_domain"

DEFAULT_MAX_FREE_ACCOUNTS_PER_DOMAIN = 3

# Observed farm domains (wordNNN@junkword-domain.com) + common temp-mail services.
DEFAULT_BLOCKED_DOMAINS = [
    # observed on production
    "bowlfuel.com", "beiwoh.com", "hutdot.com", "hgbgroup.com",
    # common disposable / temp-mail providers
    "mailinator.com", "mailinator.net", "mailinator.org",
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "temp-mail.org", "tempmail.com", "tempmail.net", "tempmail.org",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamailblock.com",
    "grr.la", "sharklasers.com", "spam4.me", "pokemail.net",
    "maildrop.cc", "mailnesia.com", "getnada.com", "nada.email",
    "yopmail.com", "yopmail.fr", "yopmail.net",
    "throwawaymail.com", "throwaway.email", "trashmail.com",
    "trashmail.de", "mailmetrash.com", "inboxkitten.com",
    "mintemail.com", "tempinbox.com", "mailtemp.net", "tempmailo.com",
    "emailondeck.com", "discard.email", "discardi.com",
    "mvrht.net", "moakt.com", "mailnator.com", "disposablemail.com",
    "dispostable.com", "emlpro.com", "dropmail.me", "mail.gy",
]

# Real consumer providers with identity/phone-backed signup cost — no cap.
DEFAULT_TRUSTED_DOMAINS = [
    "gmail.com", "googlemail.com",
    "yahoo.com", "ymail.com", "yahoo.com.ph", "yahoo.com.kh",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com",
    "aol.com", "zoho.com", "gmx.com", "gmx.net", "web.de",
    "proton.me", "protonmail.com", "protonmail.ch",
    "qq.com", "163.com", "126.com", "sina.com", "foxmail.com",
    "naver.com", "daum.net", "kakao.com",
    "yandex.com", "yandex.ru", "mail.ru",
    "camxora.com",
]


def _normalize_domain(email: str) -> str:
    """Return the lowercase bare domain from an email address."""
    domain = (email or "").rsplit("@", 1)[-1].strip().lower().lstrip("@")
    return domain


def _parse_list(raw) -> set[str]:
    """Accept a JSON-array string, a python list, or a comma-separated string."""
    if raw is None:
        return set()
    if isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        try:
            values = json.loads(str(raw))
        except (TypeError, ValueError):
            values = [v.strip() for v in str(raw).split(",") if v.strip()]
    out: set[str] = set()
    for v in values:
        s = str(v).strip().lower().lstrip("@")
        if s:
            out.add(s)
    return out


async def _read_settings(pool) -> tuple[set[str], set[str], int]:
    """(blocked, trusted, max_free) with code defaults when rows are missing."""
    blocked_raw = await pool.fetchval(
        "SELECT value FROM system_settings WHERE key = $1", _SETTINGS_KEY_BLOCKED
    )
    trusted_raw = await pool.fetchval(
        "SELECT value FROM system_settings WHERE key = $1", _SETTINGS_KEY_TRUSTED
    )
    max_raw = await pool.fetchval(
        "SELECT value FROM system_settings WHERE key = $1", _SETTINGS_KEY_MAX
    )

    blocked = _parse_list(blocked_raw) if blocked_raw is not None else set(DEFAULT_BLOCKED_DOMAINS)
    trusted = _parse_list(trusted_raw) if trusted_raw is not None else set(DEFAULT_TRUSTED_DOMAINS)

    if max_raw is None:
        max_free = DEFAULT_MAX_FREE_ACCOUNTS_PER_DOMAIN
    else:
        try:
            max_free = int(str(max_raw).strip())
        except (TypeError, ValueError):
            max_free = DEFAULT_MAX_FREE_ACCOUNTS_PER_DOMAIN
    if max_free < 1:
        max_free = DEFAULT_MAX_FREE_ACCOUNTS_PER_DOMAIN

    return blocked, trusted, max_free


async def _count_free_music_web_accounts(pool, domain: str) -> int:
    """Active music-web users on the domain without an active license."""
    row = await pool.fetchval(
        """
        SELECT count(*)::int
        FROM users u
        WHERE u.deleted_at IS NULL
          AND u.status = 'active'
          AND lower(split_part(u.email, '@', 2)) = $1
          AND $2 = ANY(u.products)
          AND NOT EXISTS (
              SELECT 1 FROM licenses l
              WHERE l.user_id = u.id AND l.status = 'active'
          )
        """,
        domain,
        MUSIC_WEB_PRODUCT,
    )
    return int(row or 0)


async def enforce_signup_domain_guard(email: str, product: str | None) -> None:
    """Reject disposable-domain and over-cap music-web signups (raises 422).

    Returns without raising when the signup is allowed.
    """
    if (product or "") != MUSIC_WEB_PRODUCT:
        return

    from platform_api.dependencies import get_db_pool
    from platform_api.exceptions import ValidationError

    domain = _normalize_domain(email)
    if not domain or "." not in domain:
        return  # malformed email is handled by normal validation

    pool = get_db_pool()
    blocked, trusted, max_free = await _read_settings(pool)

    if domain in trusted:
        return
    if domain in blocked:
        logger.warning("Blocked signup from disposable domain: domain=%s email=%s", domain, email)
        raise ValidationError(
            message="Signups from this email provider are not allowed.",
            details={"field": "email", "message": "Signups from this email provider are not allowed."},
        )

    count = await _count_free_music_web_accounts(pool, domain)
    if count >= max_free:
        logger.warning(
            "Signup domain cap hit: domain=%s count=%s max=%s email=%s",
            domain, count, max_free, email,
        )
        raise ValidationError(
            message="Too many free accounts from this email provider. Please use a different email or subscribe.",
            details={
                "field": "email",
                "message": "Too many free accounts from this email provider. Please use a different email or subscribe.",
            },
        )


async def add_blocked_email_domain(domain: str) -> tuple[bool, str]:
    """Add an email domain to the disposable signup blocklist (admin/ops action).

    Refuses trusted consumer domains. Returns (changed, message).
    """
    from platform_api.dependencies import get_db_pool

    normalized = (domain or "").strip().lower().lstrip("@")
    if not normalized or "." not in normalized:
        return False, "Not a valid email domain."
    pool = get_db_pool()
    blocked, trusted, _ = await _read_settings(pool)
    if normalized in trusted:
        return False, f"{normalized} is a trusted provider — not blocked."
    if normalized in blocked:
        return False, f"{normalized} is already blocked."
    blocked.add(normalized)
    await pool.execute(
        "INSERT INTO system_settings (key, value, value_type, updated_at) "
        "VALUES ($1, $2, 'json', NOW()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
        "value_type = 'json', updated_at = NOW()",
        _SETTINGS_KEY_BLOCKED,
        json.dumps(sorted(blocked)),
    )
    logger.warning("Blocked email domain added: domain=%s total=%s", normalized, len(blocked))
    return True, f"{normalized} added to the signup blocklist ({len(blocked)} total)."


async def suspend_user_by_id(user_id: str, reason: str) -> tuple[bool, str]:
    """Suspend one user account (admin/ops action). Reversible by an admin."""
    from platform_api.dependencies import get_db_pool

    try:
        user_uuid = UUID(str(user_id).strip())
    except (TypeError, ValueError):
        return False, "Invalid user id."
    pool = get_db_pool()
    status = await pool.execute(
        "UPDATE users SET status = 'suspended', suspension_reason = $2 "
        "WHERE id = $1 AND deleted_at IS NULL",
        user_uuid,
        str(reason or "Suspected disposable-domain signup (Telegram ops)")[:300],
    )
    if status == "UPDATE 0":
        return False, "User not found or already suspended."
    logger.warning("User suspended via ops action: user=%s reason=%s", user_uuid, reason)
    return True, "User suspended."
