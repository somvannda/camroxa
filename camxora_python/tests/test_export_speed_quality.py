"""Export speed-mode quality tradeoffs (glow passes + particle caps)."""

from __future__ import annotations

import pytest

from visualizer_video.export_gpu_tier import clear_export_gpu_tier_cache
from visualizer_video.gpu_render import (
    export_glow_pass_limit,
    export_particle_caps,
    normalize_export_speed_mode,
)


@pytest.fixture(autouse=True)
def _mid_gpu_tier(monkeypatch: pytest.MonkeyPatch):
    """Keep baseline caps stable regardless of the host GPU."""
    monkeypatch.setenv("CAMXORA_GPU_TIER", "mid")
    clear_export_gpu_tier_cache()
    yield
    clear_export_gpu_tier_cache()


def test_normalize_export_speed_mode() -> None:
    assert normalize_export_speed_mode("FAST") == "fast"
    assert normalize_export_speed_mode(None) == "balanced"
    assert normalize_export_speed_mode("nope") == "balanced"


def test_export_glow_pass_limit_by_tier() -> None:
    assert export_glow_pass_limit("very_fast") == 0
    assert export_glow_pass_limit("draft") == 0
    assert export_glow_pass_limit("fast") == 0
    assert export_glow_pass_limit("balanced") == 0
    assert export_glow_pass_limit("quality") == 2
    assert export_glow_pass_limit("master") == 2


def test_export_particle_caps_tame_bass_drive_leave_beattok() -> None:
    # Bass Drive-like: 1200 max / 400 spawn
    assert export_particle_caps("balanced", max_count=1200, spawn_rate=400.0) == (600, 200.0)
    assert export_particle_caps("fast", max_count=1200, spawn_rate=400.0) == (400, 120.0)
    assert export_particle_caps("very_fast", max_count=1200, spawn_rate=400.0) == (250, 80.0)
    # Beattok-like: under balanced caps — unchanged
    assert export_particle_caps("balanced", max_count=475, spawn_rate=100.0) == (475, 100.0)
    # Master / quality untouched
    assert export_particle_caps("quality", max_count=1200, spawn_rate=400.0) == (1200, 400.0)
    assert export_particle_caps("master", max_count=1200, spawn_rate=400.0) == (1200, 400.0)
