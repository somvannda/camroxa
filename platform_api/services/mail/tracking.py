"""Signed tokens and body instrumentation for open/click tracking.

Config-free and database-free so the security-relevant parts (signature packing,
link rewriting, redirect safety) can be unit-tested directly — same split as
``services/cutluy_webhook`` and the musicapi equivalent.

Token shape: ``<base64url(payload)>.<base64url(HMAC-SHA256(payload))>``. The
payload carries a type prefix, so a token minted for one purpose (open) can never
be replayed as another (click, unsubscribe).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html as _html
import re
from typing import Mapping
from urllib.parse import urlparse

TYPE_OPEN = "o1"
TYPE_CLICK = "c1"
TYPE_UNSUB = "u1"

_LINK_RE = re.compile(
    r'(?P<prefix><a\b[^>]*?\shref\s*=\s*)(?P<quote>["\'])(?P<href>.*?)(?P=quote)',
    re.IGNORECASE,
)
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_ESCAPE_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _mac(secret: str, value: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()


def pack(secret: str, payload: str) -> str:
    body = _b64url(payload.encode("utf-8"))
    return f"{body}.{_b64url(_mac(secret, body))}"


def unpack(secret: str, token: str) -> str | None:
    """Constant-time verification. Returns the payload, or None when untrusted."""
    if not secret or not token:
        return None
    body, _, given = token.rpartition(".")
    if not body or not given:
        return None
    expected = _b64url(_mac(secret, body))
    if not hmac.compare_digest(given, expected):
        return None
    try:
        return _b64url_decode(body).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def build_open_token(secret: str, send_id: str) -> str:
    return pack(secret, f"{TYPE_OPEN}.{send_id}")


def parse_open_token(secret: str, token: str) -> str | None:
    """Return the send id, or None when the token is not a valid open token."""
    payload = unpack(secret, token)
    if not payload:
        return None
    parts = payload.split(".")
    if len(parts) != 2 or parts[0] != TYPE_OPEN or not parts[1]:
        return None
    return parts[1]


def build_click_token(secret: str, send_id: str, url: str) -> str:
    return pack(secret, f"{TYPE_CLICK}.{send_id}.{_b64url(url.encode('utf-8'))}")


def parse_click_token(secret: str, token: str) -> tuple[str, str] | None:
    """Return ``(send_id, url)``; the URL is signed, so it cannot be tampered."""
    payload = unpack(secret, token)
    if not payload:
        return None
    parts = payload.split(".")
    if len(parts) != 3 or parts[0] != TYPE_CLICK or not parts[1] or not parts[2]:
        return None
    try:
        url = _b64url_decode(parts[2]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if not is_safe_redirect(url):
        return None
    return parts[1], url


def build_unsub_token(secret: str, user_id: str) -> str:
    return pack(secret, f"{TYPE_UNSUB}.{user_id}")


def parse_unsub_token(secret: str, token: str) -> str | None:
    payload = unpack(secret, token)
    if not payload:
        return None
    parts = payload.split(".")
    if len(parts) != 2 or parts[0] != TYPE_UNSUB or not parts[1]:
        return None
    return parts[1]


def is_safe_redirect(url: str) -> bool:
    """Only absolute http(s) destinations are ever redirected to."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _should_instrument(href: str) -> bool:
    value = href.strip()
    if not value or value.startswith("#"):
        return False
    if re.match(r"^(mailto|tel|sms):", value, re.IGNORECASE):
        return False
    if "{{" in value or "{%" in value:
        return False
    if value.startswith("/api/mail/"):
        return False
    return is_safe_redirect(value)


def instrument_html(html: str, click_url, open_url: str) -> tuple[str, int]:
    """Rewrite clickable links through the redirect and append the open pixel.

    ``click_url`` is a callable taking the destination and returning the tracking
    URL. Returns ``(html, links_rewritten)``.
    """
    links = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal links
        href = match.group("href")
        if not _should_instrument(href):
            return match.group(0)
        links += 1
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{click_url(href.strip())}{quote}"

    rewritten = _LINK_RE.sub(_replace, html)
    pixel = (
        f'<img src="{open_url}" width="1" height="1" alt="" '
        'style="display:block;width:1px;height:1px;border:0;outline:none;" />'
    )
    if re.search(r"</body>", rewritten, re.IGNORECASE):
        rewritten = re.sub(r"</body>", f"{pixel}</body>", rewritten, count=1, flags=re.IGNORECASE)
    else:
        rewritten = f"{rewritten}{pixel}"
    return rewritten, links


def escape_html(value: str) -> str:
    return "".join(_ESCAPE_MAP.get(ch, ch) for ch in value)


def render_vars(
    source: str,
    values: Mapping[str, object],
    escape: bool = True,
) -> str:
    """Replace ``{{name}}`` placeholders; unknown ones are left visible on purpose."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values or values[key] is None:
            return match.group(0)
        text = str(values[key])
        return escape_html(text) if escape else text

    return _VAR_RE.sub(_replace, source)


def html_to_text(html: str) -> str:
    """Strip tags for the plain-text alternative (no dependency)."""
    text = re.sub(r"<style\b[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<script\b[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<head\b[\s\S]*?</head>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
