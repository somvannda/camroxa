"""IP-based abuse detection for music web generation endpoints.

Tracks suspicious patterns such as:
- Multiple accounts from same IP hitting quota limits
- Rapid account creation from same IP
- Repeated failed generation attempts
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Abuse detection thresholds
MAX_ACCOUNTS_PER_IP_PER_HOUR = 5
MAX_QUOTA_HITS_PER_IP_PER_HOUR = 10
MAX_GENERATIONS_PER_IP_PER_DAY = 5  # Same as user limit
ABUSE_BLOCK_DURATION_SECONDS = 3600  # 1 hour

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
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can have multiple IPs, take the first (original client)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
        logger.warning(f"IP geolocation check failed for {ip}: {exc}")
    
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
    """Check if an IP address shows signs of abuse, VPN usage, or is outside Cambodia.

    Args:
        redis: Redis client for tracking.
        ip: Client IP address.
        user_id: Current user ID.
        event_type: Type of event ("generation", "quota_hit", "account_creation").

    Raises:
        HTTPException: 429 if IP is blocked, 403 if VPN/wrong country.
    """
    # Check geolocation and VPN (only for generation events to avoid overhead)
    if event_type == "generation":
        country_code, asn = await check_ip_geolocation(ip)
        
        # Block non-Cambodia IPs
        if country_code and country_code != ALLOWED_COUNTRY:
            logger.warning(
                f"Blocked non-Cambodia IP {ip} (country: {country_code}) "
                f"attempting generation with user {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "GEO_RESTRICTED",
                    "message": "This service is only available in Cambodia.",
                },
            )
        
        # Block VPNs and proxies
        if asn and await is_vpn_or_proxy(asn):
            logger.warning(
                f"Blocked VPN/proxy IP {ip} (ASN: {asn}) "
                f"attempting generation with user {user_id}"
            )
            await redis.setex(f"abuse:blocked:{ip}", ABUSE_BLOCK_DURATION_SECONDS, "vpn")
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "VPN_DETECTED",
                    "message": "VPN and proxy connections are not allowed. Please use a direct connection.",
                },
            )
    
    # Check if IP is currently blocked
    block_key = f"abuse:blocked:{ip}"
    blocked = await redis.get(block_key)
    if blocked:
        logger.warning(f"Blocked IP {ip} attempted {event_type} with user {user_id}")
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "IP_BLOCKED",
                "message": "Too many requests from your IP address. Please try again later.",
                "retry_after": ABUSE_BLOCK_DURATION_SECONDS,
            },
            headers={"Retry-After": str(ABUSE_BLOCK_DURATION_SECONDS)},
        )

    # Track per-IP daily generation count (5 per day limit)
    if event_type == "generation":
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        ip_daily_key = f"abuse:ip_daily:{ip}:{today}"
        ip_count = await redis.incr(ip_daily_key)
        await redis.expire(ip_daily_key, 86400)  # 24 hour TTL
        
        if ip_count > MAX_GENERATIONS_PER_IP_PER_DAY:
            logger.warning(
                f"IP {ip} exceeded daily generation limit: {ip_count}/{MAX_GENERATIONS_PER_IP_PER_DAY}"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "IP_DAILY_LIMIT",
                    "message": f"Maximum {MAX_GENERATIONS_PER_IP_PER_DAY} songs per day from one IP. Try again tomorrow.",
                    "retry_after": 86400,
                },
                headers={"Retry-After": "86400"},
            )
    
    # Track account usage per IP
    account_key = f"abuse:accounts:{ip}"
    await redis.setex(account_key, 3600, user_id)  # Track for 1 hour
    
    # Track quota hits per IP (when users hit their limit)
    if event_type == "quota_hit":
        quota_key = f"abuse:quota_hits:{ip}"
        hits = await redis.incr(quota_key)
        await redis.expire(quota_key, 3600)  # 1 hour window
        
        if hits >= MAX_QUOTA_HITS_PER_IP_PER_HOUR:
            # Block the IP - likely account cycling
            await redis.setex(block_key, ABUSE_BLOCK_DURATION_SECONDS, "1")
            logger.warning(
                f"Blocking IP {ip} for excessive quota hits: {hits} in 1 hour"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error_code": "ABUSE_DETECTED",
                    "message": "Suspicious activity detected. Your IP has been temporarily blocked.",
                    "retry_after": ABUSE_BLOCK_DURATION_SECONDS,
                },
                headers={"Retry-After": str(ABUSE_BLOCK_DURATION_SECONDS)},
            )


_redis_client: RedisClient | None = None


def configure_abuse_detection(redis: RedisClient) -> None:
    """Configure abuse detection with Redis client."""
    global _redis_client
    _redis_client = redis


async def track_generation_attempt(request: Request, user_id: str) -> None:
    """Track a generation attempt for abuse detection."""
    if _redis_client is None:
        return
    
    ip = get_client_ip(request)
    try:
        await check_ip_abuse(_redis_client, ip, user_id, "generation")
    except HTTPException:
        # Re-raise HTTP exceptions (blocks)
        raise
    except Exception as exc:
        # Log but don't block on Redis errors
        logger.error(f"Abuse detection error for IP {ip}: {exc}")


async def track_quota_exceeded(request: Request, user_id: str) -> None:
    """Track when a user hits their quota limit."""
    if _redis_client is None:
        return
    
    ip = get_client_ip(request)
    try:
        await check_ip_abuse(_redis_client, ip, user_id, "quota_hit")
    except HTTPException:
        # Re-raise HTTP exceptions (blocks)
        raise
    except Exception as exc:
        # Log but don't block on Redis errors
        logger.error(f"Abuse detection error for IP {ip}: {exc}")
