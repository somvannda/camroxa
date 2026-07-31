"""Tests for local domain preset JSON store and domain registries."""

from __future__ import annotations

from pathlib import Path

import pytest

from features.video.lib import domain_preset_store
from features.video.lib.background_style_registry import (
    capture_background_preset,
    resolve_background_preset_patch,
    restore_background_preset_to_factory,
)
from features.video.lib.domain_preset_store import (
    clear_all_domain_preset_overrides,
    get_domain_preset_override,
    save_domain_preset_override,
)
from features.video.lib.logo_style_registry import (
    capture_logo_preset,
    resolve_logo_preset_patch,
    restore_logo_preset_to_factory,
)
from features.video.lib.particle_session_presets import (
    capture_session_particle_preset,
    clear_session_particle_presets,
    resolve_particle_preset_patch,
    restore_particle_preset_to_factory,
)
from features.video.lib.particle_settings import build_particle_motion_preset_patch
from features.video.lib.spectrum_session_presets import (
    capture_session_spectrum_preset,
    clear_session_spectrum_presets,
    get_session_spectrum_preset,
    restore_spectrum_preset_to_factory,
)
from features.video.lib.text_style_registry import (
    apply_resolved_text_preset,
    capture_text_preset,
    resolve_text_preset_style,
    restore_text_preset_to_factory,
)


@pytest.fixture(autouse=True)
def _isolated_presets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(domain_preset_store, "get_video_presets_dir", lambda: tmp_path / "video-presets")
    domain_preset_store.reset_domain_preset_memory_for_tests()
    clear_session_particle_presets()
    clear_session_spectrum_presets()
    clear_all_domain_preset_overrides("background")
    clear_all_domain_preset_overrides("logo")
    clear_all_domain_preset_overrides("text")
    yield
    clear_session_particle_presets()
    clear_session_spectrum_presets()
    domain_preset_store.reset_domain_preset_memory_for_tests()


def test_domain_preset_store_round_trip(tmp_path: Path) -> None:
    save_domain_preset_override("particles", "embers", {"particlesSpeed": 9.0})
    assert get_domain_preset_override("particles", "embers")["particlesSpeed"] == 9.0
    # Session-only: must not write disk files.
    assert not (tmp_path / "video-presets" / "particles.json").is_file()


def test_domain_preset_store_is_session_memory_only(tmp_path: Path) -> None:
    save_domain_preset_override("spectrum", "orbit-spikes", {"draft": {"audioInputGain": 3.0}})
    assert get_domain_preset_override("spectrum", "orbit-spikes") is not None
    domain_preset_store.reset_domain_preset_memory_for_tests()
    assert get_domain_preset_override("spectrum", "orbit-spikes") is None
    assert not (tmp_path / "video-presets" / "spectrum.json").is_file()


def test_particle_override_survives_resolve_and_restore() -> None:
    factory = build_particle_motion_preset_patch("embers")
    assert factory is not None
    capture_session_particle_preset("embers", {**factory, "particlesSpeed": 11.0})
    restored = resolve_particle_preset_patch("embers")
    assert restored is not None
    assert restored["particlesSpeed"] == 11.0
    factory_again = restore_particle_preset_to_factory("embers")
    assert factory_again == factory
    assert resolve_particle_preset_patch("embers") == factory


def test_spectrum_override_survives_restart_shape() -> None:
    draft = {"style": "orbit-spikes", "audioInputGain": 5.5, "spectrumEnabled": True}
    layers = [{"id": "l1", "thickness": 60.0}]
    capture_session_spectrum_preset("orbit-spikes", draft, layers)
    loaded = get_session_spectrum_preset("orbit-spikes")
    assert loaded is not None
    assert loaded["draft"]["audioInputGain"] == 5.5
    assert restore_spectrum_preset_to_factory("orbit-spikes") is True
    assert get_session_spectrum_preset("orbit-spikes") is None


def test_background_preset_capture_and_restore() -> None:
    factory = resolve_background_preset_patch("dark_club")
    assert factory is not None
    capture_background_preset("dark_club", {**factory, "backgroundBrightness": 0.4})
    assert resolve_background_preset_patch("dark_club")["backgroundBrightness"] == 0.4
    restored = restore_background_preset_to_factory("dark_club")
    assert restored is not None
    assert restored["backgroundBrightness"] == factory["backgroundBrightness"]


def test_logo_preset_capture_and_restore() -> None:
    factory = resolve_logo_preset_patch("vinyl_spin")
    assert factory is not None
    capture_logo_preset("vinyl_spin", {**factory, "logoSpinSpeed": 180.0})
    assert resolve_logo_preset_patch("vinyl_spin")["logoSpinSpeed"] == 180.0
    restored = restore_logo_preset_to_factory("vinyl_spin")
    assert restored is not None
    assert restored["logoSpinSpeed"] == factory["logoSpinSpeed"]


def test_text_preset_override_and_apply() -> None:
    capture_text_preset(
        "neon_outline",
        overlays=[{"fontSize": 90, "color": "#00ff00", "strokeColor": "#000", "strokeWidth": 2, "shadow": 0.2, "animation": "pop", "anchor": "center", "x": 0, "y": 0}],
        selected_index=0,
    )
    style = resolve_text_preset_style("neon_outline")
    assert style is not None
    assert style["fontSize"] == 90
    overlays, index = apply_resolved_text_preset([], "neon_outline", selected_index=0)
    assert index == 0
    assert overlays[0]["fontSize"] == 90
    assert restore_text_preset_to_factory("neon_outline") is True
    factory_style = resolve_text_preset_style("neon_outline")
    assert factory_style is not None
    assert factory_style["fontSize"] == 72
