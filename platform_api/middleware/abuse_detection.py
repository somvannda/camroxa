"""IP-based abuse detection for music web generation and signup.

Tracks suspicious patterns such as:
- Rapid account creation from the same IP
- Multiple free accounts generating from the same network
- Repeated quota-limit cycling
"""

from __future__ import annotations

import logging
from typing import Protocol

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Abuse detection thresholds (signup farm protection — do not loosen)
MAX_ACCOUNTS_PER_IP_PER_HOUR = 3
MAX_ACCOUNTS_PER_IP_PER_DAY = 5
MAX_QUOTA_HITS_PER_IP_PER_HOUR = 10
MAX_GENERATIONS_PER_IP_PER_DAY = 5  # Matches one free account's daily song cap
ABUSE_BLOCK_DURATION_SECONDS = 3600  # 1 hour

# Geo / VPN at the IP-lookup layer stay off. KH-only + Tor/unknown
# blocking is MusicWebGeoMiddleware (Cloudflare CF-IPCountry).
ENABLE_GEO_RESTRICT = False
ENABLE_VPN_BLOCK = False

# Cambodia country code
ALLOWED_COUNTRY = "KH"  # Cambodia ISO code

# Common VPN/Proxy indicators
VPN_ASN_PATTERNS = [
    "digitalocean", "amazon", "google cloud", "microsoft azure",
    "linode", "vultr", "ovh", "hetzner", "vpn", "proxy", "tor"
]


class RedisClient(Protocol):
    """Protocol for async Redis client."""

    async def get(self, name: str) -> str | bytes | None: ...
    async def setex(self, name: str, time: int, value: str) -> None: ...
    async def incr(self, name: str) -> int: ...
    async def expire(self, name: str, time: int) -> None: ...


def get_client_ip(request: Request) -> str:
    """Extract client IP, preferring Cloudflare CF-Connecting-IP."""
    from platform_api.middleware.geo_access import client_ip

    return client_ip(request)


async def _freeze_signup_farm_ip(ip: str, count: int) -> None:
    """Extra generate freeze after the existing signup cap already fired.

    Does not change MAX_ACCOUNTS_PER_IP_PER_HOUR (3) or per-day (5).
    Those 429s remain the signup gate.
    """
    from platform_api.services.generation_freeze import freeze_generation

    try:
        await freeze_generation(user_id=None, ip=ip, reason="signup_farm")
    except Exception:
        logger.debug("Signup-farm freeze skipped for IP %s count=%s", ip, count)


def _billing_hour_stamp() -> str:
    from datetime import datetime

    from platform_api.services.billing_calendar import BILLING_TIMEZONE

    return datetime.now(BILLING_TIMEZONE).strftime("%Y%m%d%H")


def _billing_day_stamp() -> str:
    from platform_api.services.billing_calendar import billing_today

    return billing_today().isoformat()


def _too_many(error_code: str, message: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "error_code": error_code,
            "message": message,
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


async def check_ip_geolocation(ip: str) -> tuple[str, str]:
    """Check IP geolocation. Returns (country_code, asn_description).

    Uses ip-api.com free tier (45 requests/minute).
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,as"}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    country_code = data.get("countryCode", "").upper()
                    asn = data.get("as", "").lower()
                    return country_code, asn
    except Exception as exc:
        logger.warning("IP geolocation check failed for %s: %s", ip, exc)

    return "", ""


async def is_vpn_or_proxy(asn: str) -> bool:
    """Check if ASN indicates VPN/proxy/datacenter."""
    asn_lower = asn.lower()
    return any(pattern in asn_lower for pattern in VPN_ASN_PATTERNS)


async def check_ip_abuse(
    redis: RedisClient,
    ip: str,
    user_id: str,
    event_type: str = "generation",
) -> None:
    """Check if an IP address shows signs of signup or generation farming.

    Raises:
        HTTPException: 429 if IP is blocked or over a farm cap.
    """
    if event_type == "generation" and (ENABLE_GEO_RESTRICT or ENABLE_VPN_BLOCK):
        country_code, asn = await check_ip_geolocation(ip)

        if ENABLE_GEO_RESTRICT and country_code and country_code != ALLOWED_COUNTRY:
            logger.warning(
                "Blocked non-Cambodia IP %s (country: %s) user=%s",
                ip,
                country_code,
                user_id,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "GEO_RESTRICTED",
                    "message": "This service is only available in Cambodia.",
                },
            )

        if ENABLE_VPN_BLOCK and asn and await is_vpn_or_proxy(asn):
            logger.warning("Blocked VPN/proxy IP %s (ASN: %s) user=%s", ip, asn, user_id)
            await redis.setex(f"abuse:blocked:{ip}", ABUSE_BLOCK_DURATION_SECONDS, "vpn")
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "VPN_DETECTED",
                    "message": "VPN and proxy connections are not allowed. Please use a direct connection.",
                },
            )

    block_key = f"abuse:blocked:{ip}"
    blocked = await redis.get(block_key)
    if blocked:
        logger.warning("Blocked IP %s attempted %s with user %s", ip, event_type, user_id)
        raise _too_many(
            "IP_BLOCKED",
            "Too many requests from your IP address. Please try again later.",
            ABUSE_BLOCK_DURATION_SECONDS,
        )

    if event_type == "account_creation":
        # Signup farm protection: 3 successful accounts/hour and 5/day per IP.
        # Generate freeze below is extra; it must not replace these 429s.
        hour_key = f"abuse:signup_hour:{ip}:{_billing_hour_stamp()}"
        day_key = f"abuse:signup_day:{ip}:{_billing_day_stamp()}"
        hour_count = await redis.incr(hour_key)
        await redis.expire(hour_key, 3600)
        day_count = await redis.incr(day_key)
        await redis.expire(day_key, 90000)
        if hour_count > MAX_ACCOUNTS_PER_IP_PER_HOUR:
            logger.warning(
                "IP %s exceeded hourly signup cap: %s/%s",
                ip,
                hour_count,
                MAX_ACCOUNTS_PER_IP_PER_HOUR,
            )
            await _freeze_signup_farm_ip(ip, hour_count)
            raise _too_many(
                "SIGNUP_IP_LIMIT",
                f"Too many accounts from this network. Limit is {MAX_ACCOUNTS_PER_IP_PER_HOUR} per hour.",
                3600,
            )
        if day_count > MAX_ACCOUNTS_PER_IP_PER_DAY:
            logger.warning(
                "IP %s exceeded daily signup cap: %s/%s",
                ip,
                day_count,
                MAX_ACCOUNTS_PER_IP_PER_DAY,
            )
            await _freeze_signup_farm_ip(ip, day_count)
            raise _too_many(
                "SIGNUP_IP_DAILY_LIMIT",
                f"Too many accounts from this network. Limit is {MAX_ACCOUNTS_PER_IP_PER_DAY} per day.",
                86400,
            )
        return

    if event_type == "generation":
        ip_daily_key = f"abuse:ip_daily:{ip}:{_billing_day_stamp()}"
        ip_count = await redis.incr(ip_daily_key)
        await redis.expire(ip_daily_key, 90000)

        if ip_count > MAX_GENERATIONS_PER_IP_PER_DAY:
            logger.warning(
                "IP %s exceeded daily generation limit: %s/%s",
                ip,
                ip_count,
                MAX_GENERATIONS_PER_IP_PER_DAY,
            )
            raise _too_many(
                "IP_DAILY_LIMIT",
                f"Maximum {MAX_GENERATIONS_PER_IP_PER_DAY} free songs per day from one network. Try again tomorrow or subscribe.",
                86400,
            )

    if event_type == "quota_hit":
        quota_key = f"abuse:quota_hits:{ip}"
        hits = await redis.incr(quota_key)
        await redis.expire(quota_key, 3600)

        if hits >= MAX_QUOTA_HITS_PER_IP_PER_HOUR:
            await redis.setex(block_key, ABUSE_BLOCK_DURATION_SECONDS, "1")
            logger.warning("Blocking IP %s for excessive quota hits: %s in 1 hour", ip, hits)
            raise _too_many(
                "ABUSE_DETECTED",
                "Suspicious activity detected. Your IP has been temporarily blocked.",
                ABUSE_BLOCK_DURATION_SECONDS,
            )


_redis_client: RedisClient | None = None


def configure_abuse_detection(redis: RedisClient) -> None:
    """Configure abuse detection with Redis client."""
    global _redis_client
    _redis_client = redis


async def _run_abuse_check(request: Request, user_id: str, event_type: str) -> None:
    if _redis_client is None:
        return
    ip = get_client_ip(request)
    try:
        await check_ip_abuse(_redis_client, ip, user_id, event_type)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Abuse detection error for IP %s: %s", ip, exc)


async def track_generation_attempt(request: Request, user_id: str) -> None:
    """Track a generation attempt for abuse detection."""
    await _run_abuse_check(request, user_id, "generation")


async def track_quota_exceeded(request: Request, user_id: str) -> None:
    """Track when a user hits their quota limit."""
    await _run_abuse_check(request, user_id, "quota_hit")
    try:
        from platform_api.services.generation_freeze import note_quota_hammer

        await note_quota_hammer(request, user_id)
    except Exception:
        logger.debug("Quota-hammer freeze tracking skipped for user %s", user_id)


async def track_account_creation(request: Request) -> None:
    """Track a successful-path signup attempt for per-IP farm limits."""
    await _run_abuse_check(request, "", "account_creation")
