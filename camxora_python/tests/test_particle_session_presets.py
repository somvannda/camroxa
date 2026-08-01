from __future__ import annotations

from pathlib import Path

import pytest

from features.video.lib import domain_preset_store
from features.video.lib.particle_session_presets import (
    capture_session_particle_preset,
    clear_session_particle_presets,
    get_session_particle_preset_patch,
    resolve_particle_preset_patch,
    restore_particle_preset_to_factory,
)
from features.video.lib.particle_settings import build_particle_motion_preset_patch
from features.video.lib.particle_style_registry import (
    build_builtin_particle_preset_patch,
    is_builtin_particle_preset_key,
    resolve_active_particle_preset_key,
)


@pytest.fixture(autouse=True)
def _isolated_presets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(domain_preset_store, "get_video_presets_dir", lambda: tmp_path / "video-presets")
    domain_preset_store.reset_domain_preset_memory_for_tests()
    clear_session_particle_presets()
    yield
    clear_session_particle_presets()
    domain_preset_store.reset_domain_preset_memory_for_tests()


def test_session_override_survives_switch_away_and_back() -> None:
    factory = build_particle_motion_preset_patch("embers")
    tweaked = {**factory, "particlesSpeed": 9.5, "particlesColor": "#ff0000"}
    capture_session_particle_preset("embers", tweaked)

    dust = resolve_particle_preset_patch("dust_field")
    assert dust is not None
    assert dust["particlesStyle"] == "glow"

    restored = build_builtin_particle_preset_patch("embers")
    assert restored is not None
    assert restored["particlesSpeed"] == 9.5
    assert restored["particlesColor"] == "#ff0000"
    assert factory["particlesSpeed"] != 9.5


def test_session_presets_clear_restores_factory() -> None:
    factory = build_particle_motion_preset_patch("embers")
    capture_session_particle_preset("embers", {**factory, "particlesSpeed": 12.0})
    assert get_session_particle_preset_patch("embers") is not None
    clear_session_particle_presets()
    restored = resolve_particle_preset_patch("embers")
    assert restored == factory


def test_active_preset_key_matches_session_override() -> None:
    factory = build_particle_motion_preset_patch("embers")
    tweaked = {**factory, "particlesOpacity": 0.33}
    capture_session_particle_preset("embers", tweaked)
    assert resolve_active_particle_preset_key(tweaked) == "embers"
    assert resolve_active_particle_preset_key(factory) is None
    applied = build_builtin_particle_preset_patch("embers")
    assert applied is not None
    assert resolve_active_particle_preset_key(applied) == "embers"


def test_capture_keeps_factory_when_draft_field_is_none() -> None:
    factory = build_particle_motion_preset_patch("embers")
    assert factory is not None
    capture_session_particle_preset("embers", {**factory, "particlesSpeed": 8.0, "particlesColor": None})
    stored = get_session_particle_preset_patch("embers")
    assert stored is not None
    assert stored["particlesSpeed"] == 8.0
    assert stored["particlesColor"] == factory["particlesColor"]


def test_is_builtin_particle_preset_key() -> None:
    assert is_builtin_particle_preset_key("embers") is True
    assert is_builtin_particle_preset_key("pack:foo::1.0.0") is False
    assert is_builtin_particle_preset_key(None) is False


def test_switch_back_restores_after_capture_without_exact_factory_match() -> None:
    factory = build_particle_motion_preset_patch("embers")
    assert factory is not None
    tweaked = {**factory, "particlesSpeed": 11.0, "particlesReactStrength": 0.9}
    assert resolve_active_particle_preset_key(tweaked) is None
    capture_session_particle_preset("embers", tweaked)
    restored = build_builtin_particle_preset_patch("embers")
    assert restored is not None
    assert restored["particlesSpeed"] == 11.0
    assert resolve_active_particle_preset_key(restored) == "embers"


def test_restore_particle_preset_to_factory() -> None:
    factory = build_particle_motion_preset_patch("embers")
    capture_session_particle_preset("embers", {**factory, "particlesSpeed": 20.0})
    restored = restore_particle_preset_to_factory("embers")
    assert restored == factory
