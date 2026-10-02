"""Spectrum domain option lists."""

from __future__ import annotations

SPECTRUM_MOTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("none", "None"),
    ("zoom", "Zoom"),
)


def spectrum_audio_zoom_scale(
    *,
    mode: str | None,
    zoom_strength: float,
    audio_env: float,
) -> float:
    """Uniform spectrum size scale from audio (1.0 = no zoom)."""
    key = str(mode or "none").strip().lower()
    if key not in ("zoom", "both"):
        return 1.0
    strength = float(max(0.0, min(20.0, float(zoom_strength or 0.0))))
    env = float(max(0.0, min(1.0, float(audio_env or 0.0))))
    # Stronger than background zoom so strength 1 reads clearly on rings.
    delta = env * 0.22 * strength
    return float(max(0.35, min(3.0, 1.0 + delta)))


def step_spectrum_zoom_env(
    current: float,
    *,
    target: float,
    speed: float,
    dt: float,
) -> float:
    """Advance zoom envelope toward bass/kick. Higher speed = snappier (not slower)."""
    cur = float(max(0.0, min(1.0, current)))
    tgt = float(max(0.0, min(1.0, target)))
    spd = float(max(0.25, min(8.0, float(speed or 1.0))))
    # speed 1 ≈ medium; speed 3–4 feels immediate on kicks.
    alpha = float(1.0 - pow(0.001, max(1e-4, float(dt) * spd * 2.8)))
    alpha = float(max(0.0, min(1.0, alpha)))
    return float(cur + (tgt - cur) * alpha)
