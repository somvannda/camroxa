"""Retry/backoff helpers for image provider calls."""

from __future__ import annotations

from platform_api.exceptions import ExternalServiceError


def provider_max_attempts(
    provider: str,
    *,
    slai_retries: int,
    fallback_retries: int,
) -> int:
    normalized = str(provider or "").strip().lower()
    if normalized == "slai":
        return max(1, int(slai_retries))
    return max(1, int(fallback_retries))


def compute_retry_delay_seconds(
    exc: ExternalServiceError,
    *,
    attempt_index: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> float:
    """Exponential backoff with optional Retry-After hint from provider details."""
    details = exc.details or {}
    retry_after = details.get("retry_after_seconds")
    if retry_after is not None:
        try:
            hinted = float(retry_after)
            if hinted > 0:
                return min(max_delay_seconds, max(base_delay_seconds, hinted))
        except (TypeError, ValueError):
            pass

    delay = base_delay_seconds * (2 ** max(0, attempt_index))
    return min(max_delay_seconds, max(base_delay_seconds, delay))
