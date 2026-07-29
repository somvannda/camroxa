"""Tests for spectrum preset overrides (session memory)."""

from __future__ import annotations

from pathlib import Path

import pytest

from features.video.lib import domain_preset_store
from features.video.lib.spectrum_session_presets import (
    capture_session_spectrum_preset,
    clear_session_spectrum_presets,
    get_session_spectrum_preset,
    is_session_spectrum_preset_key,
    restore_spectrum_preset_to_factory,
    spectrum_patch_touches_preset_fields,
)


@pytest.fixture(autouse=True)
def _isolated_presets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(domain_preset_store, "get_video_presets_dir", lambda: tmp_path / "video-presets")
    domain_preset_store.reset_domain_preset_memory_for_tests()
    clear_session_spectrum_presets()
    yield
    clear_session_spectrum_presets()
    domain_preset_store.reset_domain_preset_memory_for_tests()


def test_session_override_survives_switch_away_and_back() -> None:
    draft = {
        "style": "orbit-spikes",
        "audioInputGain": 4.5,
        "spectrumEnabled": True,
        "anchor": "center",
        "positionX": 12,
        "positionY": -8,
    }
    layers = [{"id": "l1", "thickness": 55.0, "barWidth": 6.0}]
    capture_session_spectrum_preset("orbit-spikes", draft, layers)

    assert get_session_spectrum_preset("signal-needles") is None

    restored = get_session_spectrum_preset("orbit-spikes")
    assert restored is not None
    assert restored["draft"]["audioInputGain"] == 4.5
    assert restored["draft"]["positionX"] == 12
    assert restored["layers"][0]["thickness"] == 55.0


def test_legacy_style_id_aliases_into_camxora_session_slot() -> None:
    capture_session_spectrum_preset(
        "classic-vertical",
        {"style": "classic-vertical", "audioInputGain": 2.0},
        [{"id": "legacy"}],
    )
    # classic-vertical aliases to orbit-spikes for marketplace continuity
    restored = get_session_spectrum_preset("orbit-spikes")
    assert restored is not None
    assert restored["draft"]["audioInputGain"] == 2.0


def test_session_presets_clear_restores_empty() -> None:
    capture_session_spectrum_preset(
        "plasma-bloom",
        {"style": "plasma-bloom", "audioKickImpact": 2.0},
        [{"id": "a"}],
    )
    assert get_session_spectrum_preset("plasma-bloom") is not None
    clear_session_spectrum_presets()
    assert get_session_spectrum_preset("plasma-bloom") is None


def test_is_session_spectrum_preset_key() -> None:
    assert is_session_spectrum_preset_key("orbit-spikes") is True
    assert is_session_spectrum_preset_key("classic-vertical") is True
    assert is_session_spectrum_preset_key("triple-halo-orbit") is True
    assert is_session_spectrum_preset_key("triple-neon-halo") is True
    assert is_session_spectrum_preset_key("pack:foo::1.0.0") is False
    assert is_session_spectrum_preset_key(None) is False


def test_spectrum_patch_touches_preset_fields() -> None:
    assert spectrum_patch_touches_preset_fields({"audioInputGain": 2.0}) is True
    assert spectrum_patch_touches_preset_fields({"particlesSpeed": 1.0}) is False


def test_stacked_preset_session_round_trip() -> None:
    draft = {"style": "ignition-flare", "audioInputGain": 3.0}
    layers = [
        {"id": "stack-1", "thickness": 40.0},
        {"id": "stack-2", "thickness": 28.0},
    ]
    capture_session_spectrum_preset("triple-halo-orbit", draft, layers)
    restored = get_session_spectrum_preset("triple-halo-orbit")
    assert restored is not None
    assert len(restored["layers"]) == 2
    assert restored["layers"][1]["thickness"] == 28.0


def test_restore_spectrum_preset_to_factory() -> None:
    capture_session_spectrum_preset(
        "orbit-spikes",
        {"style": "orbit-spikes", "audioInputGain": 9.0},
        [{"id": "x"}],
    )
    assert restore_spectrum_preset_to_factory("orbit-spikes") is True
    assert get_session_spectrum_preset("orbit-spikes") is None
