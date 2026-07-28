"""Export GPU tier detection + low-tier particle/pipe caps."""

from __future__ import annotations

import pytest

from visualizer.export_gpu_tier import (
    classify_export_gpu_tier,
    clear_export_gpu_tier_cache,
    detect_export_gpu_tier,
)
from visualizer.gpu_render import export_particle_caps
from visualizer.readback import resolve_pipe_pix_fmt


@pytest.fixture(autouse=True)
def _clear_tier_cache(monkeypatch: pytest.MonkeyPatch):
    clear_export_gpu_tier_cache()
    monkeypatch.delenv("CAMXORA_GPU_TIER", raising=False)
    yield
    clear_export_gpu_tier_cache()


def test_classify_low_by_1050_name() -> None:
    assert classify_export_gpu_tier(name="NVIDIA GeForce GTX 1050 Ti", memory_mib=4096) == "low"


def test_classify_low_by_vram_under_6gb() -> None:
    assert classify_export_gpu_tier(name="Unknown GPU", memory_mib=4096) == "low"


def test_classify_high_by_3060_name() -> None:
    assert classify_export_gpu_tier(name="NVIDIA GeForce RTX 3060", memory_mib=12288) == "high"


def test_classify_mid_default() -> None:
    assert classify_export_gpu_tier(name="NVIDIA GeForce GTX 1660", memory_mib=6144) == "mid"


def test_detect_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_TIER", "low")
    clear_export_gpu_tier_cache()
    assert detect_export_gpu_tier() == "low"
    monkeypatch.setenv("CAMXORA_GPU_TIER", "high")
    clear_export_gpu_tier_cache()
    assert detect_export_gpu_tier() == "high"


def test_low_tier_tightens_particle_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_TIER", "low")
    clear_export_gpu_tier_cache()
    assert export_particle_caps("balanced", max_count=1200, spawn_rate=400.0) == (350, 100.0)
    assert export_particle_caps("fast", max_count=1200, spawn_rate=400.0) == (250, 80.0)
    assert export_particle_caps("very_fast", max_count=1200, spawn_rate=400.0) == (150, 50.0)
    # Master untouched
    assert export_particle_caps("master", max_count=1200, spawn_rate=400.0) == (1200, 400.0)


def test_mid_tier_keeps_existing_particle_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_TIER", "mid")
    clear_export_gpu_tier_cache()
    assert export_particle_caps("balanced", max_count=1200, spawn_rate=400.0) == (600, 200.0)
    assert export_particle_caps("fast", max_count=1200, spawn_rate=400.0) == (400, 120.0)


def test_low_tier_quality_pipe_prefers_yuv420p(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_TIER", "low")
    clear_export_gpu_tier_cache()
    monkeypatch.delenv("CAMXORA_EXPORT_PIPE", raising=False)
    assert resolve_pipe_pix_fmt("quality") == "yuv420p"


def test_high_tier_quality_pipe_stays_rgba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_GPU_TIER", "high")
    clear_export_gpu_tier_cache()
    monkeypatch.delenv("CAMXORA_EXPORT_PIPE", raising=False)
    assert resolve_pipe_pix_fmt("quality") == "rgba"


def test_resolve_pipeline_export_workers_forces_one_on_low(monkeypatch: pytest.MonkeyPatch) -> None:
    from visualizer.export_gpu_tier import resolve_pipeline_export_workers

    monkeypatch.setenv("CAMXORA_GPU_TIER", "low")
    clear_export_gpu_tier_cache()
    assert resolve_pipeline_export_workers(4) == 1

    monkeypatch.setenv("CAMXORA_GPU_TIER", "mid")
    clear_export_gpu_tier_cache()
    assert resolve_pipeline_export_workers(3) == 3


def test_resolve_pipeline_export_workers_honors_prefs_when_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from visualizer.export_gpu_tier import resolve_pipeline_export_workers

    monkeypatch.setenv("CAMXORA_GPU_TIER", "high")
    clear_export_gpu_tier_cache()
    monkeypatch.setattr(
        "shared.lib.runtime_paths.is_frozen_runtime",
        lambda: True,
    )
    assert resolve_pipeline_export_workers(4) == 4
