"""Export quality tiers — Draft / Standard / Master presets."""

from __future__ import annotations

from dataclasses import dataclass

from shared.lib.export_codec import normalize_export_speed_mode

EXPORT_TIER_CHOICES = ("draft", "standard", "master")
DEFAULT_PIPELINE_EXPORT_TIER = "draft"
DEFAULT_MANUAL_EXPORT_TIER = "standard"


@dataclass(frozen=True)
class ExportTierSettings:
    tier: str
    resolution: str
    fps: int
    speed_mode: str
    label: str


def normalize_export_tier(value: object, *, default: str = "standard") -> str:
    tier = str(value or default).strip().lower()
    if tier in EXPORT_TIER_CHOICES:
        return tier
    return default if default in EXPORT_TIER_CHOICES else "standard"


def resolve_export_tier_settings(
    settings: dict | None,
    *,
    pipeline: bool = False,
) -> ExportTierSettings:
    """Map tier + user overrides to concrete export parameters."""
    raw = settings or {}
    default_tier = DEFAULT_PIPELINE_EXPORT_TIER if pipeline else DEFAULT_MANUAL_EXPORT_TIER
    tier = normalize_export_tier(raw.get("videoExportTier"), default=default_tier)

    def _fps_from_settings(*, default: int = 24) -> int:
        try:
            return int(raw.get("videoExportFps", default))
        except (TypeError, ValueError):
            return int(default)

    if tier == "draft":
        # Draft stays a fixed fast preset (preview / pipeline default).
        resolution = str(raw.get("videoExportDraftResolution") or "1280x720").strip() or "1280x720"
        fps = 24
        speed_mode = "very_fast"
        label = "Draft"
    elif tier == "master":
        resolution = str(raw.get("outputResolution") or "1920x1080").strip() or "1920x1080"
        fps = _fps_from_settings(default=24)
        speed_mode = normalize_export_speed_mode(raw.get("videoExportSpeedMode"), default="balanced")
        label = "Master"
    else:
        # Standard: Preferences resolution + Video page FPS / speed.
        tier = "standard"
        resolution = str(raw.get("outputResolution") or "1920x1080").strip() or "1920x1080"
        fps = _fps_from_settings(default=24)
        speed_mode = normalize_export_speed_mode(raw.get("videoExportSpeedMode"), default="balanced")
        label = "Standard"

    return ExportTierSettings(
        tier=tier,
        resolution=resolution,
        fps=fps,
        speed_mode=speed_mode,
        label=label,
    )
