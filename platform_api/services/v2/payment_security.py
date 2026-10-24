"""Shared guards for music-web KHQR checkout and top-up."""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

_PAYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{4,128}$")

ALLOWED_MUSIC_WEB_RETURN_HOSTS = frozenset(
    {
        "music.camxora.com",
        "music.sandbox.camxora.com",
    }
)

DEFAULT_MUSIC_WEB_RETURN_URL = "https://music.camxora.com/create"


def validate_payment_id(payment_id: str | None) -> str:
    """Reject path-traversal / SSRF payment ids before they hit CutLuy."""
    value = str(payment_id or "").strip()
    if not _PAYMENT_ID_RE.fullmatch(value):
        raise ValueError("Invalid payment id")
    return value


def is_allowed_cutluy_checkout_url(url: str | None) -> bool:
    """Only CutLuy HTTPS checkout pages may be returned to the browser."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    return host == "cutluy.com" or host.endswith(".cutluy.com")


def require_cutluy_checkout_url(url: str | None) -> str:
    value = str(url or "").strip()
    if not is_allowed_cutluy_checkout_url(value):
        raise ValueError("Payment provider returned an invalid checkout URL")
    return value


def _is_allowed_chmaba_host(host: str | None, api_base_url: str | None = None) -> bool:
    host = (host or "").lower()
    if not host:
        return False
    if host == "chmaba.com" or host.endswith(".chmaba.com"):
        return True
    # A self-hosted or staging gateway is trusted only when it is the host the
    # admin configured as the API base, never one echoed back by the provider.
    base_host = (urlparse(str(api_base_url or "").strip()).hostname or "").lower()
    return bool(base_host) and host == base_host


def is_allowed_chmaba_checkout_url(
    url: str | None,
    *,
    api_base_url: str | None = None,
) -> bool:
    """Only ChmabaPay HTTPS checkout pages may be returned to the browser."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    return _is_allowed_chmaba_host(parsed.hostname, api_base_url)


def require_chmaba_checkout_url(
    url: str | None,
    *,
    api_base_url: str | None = None,
) -> str:
    value = str(url or "").strip()
    if not is_allowed_chmaba_checkout_url(value, api_base_url=api_base_url):
        parsed = urlparse(value)
        logger.warning(
            "ChmabaPay checkout URL rejected: scheme=%r host=%r value=%r",
            parsed.scheme,
            parsed.hostname,
            value[:160],
        )
        raise ValueError("Payment provider returned an invalid checkout URL")
    return value


def resolve_chmaba_checkout_url(
    url: str | None,
    *,
    api_base_url: str,
) -> str:
    """Turn the provider's checkout link into an absolute, validated URL.

    ChmabaPay answers ``POST /api/v1/payments`` with a same-origin relative
    path (``/pay/{id}``), not a full URL. Left relative, the browser would
    resolve it against the calling site, so prepend the configured gateway
    origin and then apply the usual allowlist.
    """
    value = str(url or "").strip()
    if not value:
        raise ValueError("Payment provider returned an invalid checkout URL")
    if value.startswith("/") and not value.startswith("//"):
        value = f"{str(api_base_url or '').rstrip('/')}{value}"

    # ChmabaPay answers with `http://pay.chmaba.com/pay/{id}` (verified against
    # musicapi's stored payments). Serving that from an HTTPS page would be
    # blocked as mixed content, and we would be shipping the payer a plaintext
    # payment page, so upgrade the scheme before validating the host.
    parsed = urlparse(value)
    if (
        parsed.scheme == "http"
        and not parsed.username
        and not parsed.password
        and _is_allowed_chmaba_host(parsed.hostname, api_base_url)
    ):
        value = urlunparse(
            ("https", parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
        )

    return require_chmaba_checkout_url(value, api_base_url=api_base_url)


def sanitize_music_web_return_url(
    raw: str | None,
    *,
    fallback: str = DEFAULT_MUSIC_WEB_RETURN_URL,
) -> str:
    """Ignore attacker-controlled redirects; keep only music-web origins."""
    parsed = urlparse(str(raw or "").strip())
    host = (parsed.hostname or "").lower()
    scheme = (parsed.scheme or "").lower()
    if parsed.username or parsed.password:
        return fallback

    path = parsed.path or "/create"
    if not path.startswith("/") or path.startswith("//") or ".." in path or "\\" in path:
        path = "/create"

    if host in {"localhost", "127.0.0.1"} and scheme in {"http", "https"}:
        return urlunparse((scheme, parsed.netloc, path, "", "", ""))
    if scheme == "https" and host in ALLOWED_MUSIC_WEB_RETURN_HOSTS:
        return urlunparse(("https", host, path, "", "", ""))
    return fallback


def extract_paid_amount_cents(payload: Mapping[str, Any] | None) -> int | None:
    """Read CutLuy amount as cents. `amount` is dollars; `amount_cents` wins."""
    if not payload:
        return None
    data: Any = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, Mapping):
        return None

    for key in ("amount_cents", "amount_in_cents"):
        raw = data.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    raw_amount = data.get("amount")
    if raw_amount is None:
        return None
    try:
        return int(round(float(raw_amount) * 100))
    except (TypeError, ValueError):
        return None


def paid_amount_matches(expected_cents: int, payload: Mapping[str, Any] | None) -> bool:
    """If CutLuy reports an amount, it must match the local plan/pack price."""
    paid = extract_paid_amount_cents(payload)
    if paid is None:
        return True
    return abs(int(expected_cents) - paid) <= 1


def webhook_user_matches(row_user_id: str, payload: Mapping[str, Any] | None) -> bool:
    if not payload:
        return True
    data: Any = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, Mapping):
        return True
    metadata = data.get("metadata")
    if not isinstance(metadata, Mapping):
        return True
    meta_user = metadata.get("user_id")
    if meta_user is None or str(meta_user).strip() == "":
        return True
    return str(meta_user) == str(row_user_id)
