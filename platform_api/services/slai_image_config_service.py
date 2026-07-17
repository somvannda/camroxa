"""Admin-managed SLAI image provider throttling and retry configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from platform_api.config import Settings, get_settings
from platform_api.services.slai_image_rate_limiter import configure_slai_image_rate_limit

SETTINGS_KEY = "slai_image_provider_config"

_CACHE: "SlaiImageProviderConfig | None" = None


@dataclass(frozen=True, slots=True)
class SlaiImageProviderConfig:
    min_interval_seconds: float
    max_concurrent: int
    provider_retries: int
    retry_base_delay_seconds: float
    retry_max_delay_seconds: float
    fallback_provider_retries: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "min_interval_seconds": self.min_interval_seconds,
            "max_concurrent": self.max_concurrent,
            "provider_retries": self.provider_retries,
            "retry_base_delay_seconds": self.retry_base_delay_seconds,
            "retry_max_delay_seconds": self.retry_max_delay_seconds,
            "fallback_provider_retries": self.fallback_provider_retries,
        }


class SettingsRepoProtocol(Protocol):
    async def get_system_setting(self, key: str) -> Any | None: ...
    async def upsert_system_settings(self, settings: dict[str, Any]) -> None: ...


def defaults_from_env(settings: Settings | None = None) -> SlaiImageProviderConfig:
    app_settings = settings or get_settings()
    return SlaiImageProviderConfig(
        min_interval_seconds=float(app_settings.slai_image_min_interval_seconds),
        max_concurrent=int(app_settings.slai_image_max_concurrent),
        provider_retries=int(app_settings.slai_image_provider_retries),
        retry_base_delay_seconds=float(app_settings.slai_image_retry_base_delay_seconds),
        retry_max_delay_seconds=float(app_settings.slai_image_retry_max_delay_seconds),
        fallback_provider_retries=int(app_settings.image_fallback_provider_retries),
    )


def _coerce_float(value: Any, *, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def _coerce_int(value: Any, *, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def normalize_config(
    raw: Any,
    *,
    defaults: SlaiImageProviderConfig | None = None,
) -> SlaiImageProviderConfig:
    base = defaults or defaults_from_env()
    payload = raw if isinstance(raw, dict) else {}
    return SlaiImageProviderConfig(
        min_interval_seconds=_coerce_float(
            payload.get("min_interval_seconds"),
            fallback=base.min_interval_seconds,
            minimum=0.0,
            maximum=120.0,
        ),
        max_concurrent=_coerce_int(
            payload.get("max_concurrent"),
            fallback=base.max_concurrent,
            minimum=1,
            maximum=8,
        ),
        provider_retries=_coerce_int(
            payload.get("provider_retries"),
            fallback=base.provider_retries,
            minimum=1,
            maximum=20,
        ),
        retry_base_delay_seconds=_coerce_float(
            payload.get("retry_base_delay_seconds"),
            fallback=base.retry_base_delay_seconds,
            minimum=0.0,
            maximum=120.0,
        ),
        retry_max_delay_seconds=_coerce_float(
            payload.get("retry_max_delay_seconds"),
            fallback=base.retry_max_delay_seconds,
            minimum=1.0,
            maximum=300.0,
        ),
        fallback_provider_retries=_coerce_int(
            payload.get("fallback_provider_retries"),
            fallback=base.fallback_provider_retries,
            minimum=1,
            maximum=5,
        ),
    )


def apply_slai_image_provider_config(config: SlaiImageProviderConfig) -> None:
    configure_slai_image_rate_limit(
        min_interval_seconds=config.min_interval_seconds,
        max_concurrent=config.max_concurrent,
    )


def get_cached_slai_image_provider_config() -> SlaiImageProviderConfig:
    if _CACHE is None:
        config = defaults_from_env()
        apply_slai_image_provider_config(config)
        return config
    return _CACHE


def set_cached_slai_image_provider_config(config: SlaiImageProviderConfig) -> SlaiImageProviderConfig:
    global _CACHE
    normalized = normalize_config(config.to_dict(), defaults=config)
    _CACHE = normalized
    apply_slai_image_provider_config(normalized)
    return normalized


async def load_slai_image_provider_config(
    repo: SettingsRepoProtocol | None,
    *,
    settings: Settings | None = None,
) -> SlaiImageProviderConfig:
    defaults = defaults_from_env(settings)
    raw = None
    if repo is not None:
        raw = await repo.get_system_setting(SETTINGS_KEY)
    config = normalize_config(raw, defaults=defaults)
    return set_cached_slai_image_provider_config(config)


async def save_slai_image_provider_config(
    repo: SettingsRepoProtocol,
    payload: dict[str, Any],
) -> SlaiImageProviderConfig:
    config = normalize_config(payload)
    await repo.upsert_system_settings({SETTINGS_KEY: config.to_dict()})
    return set_cached_slai_image_provider_config(config)
