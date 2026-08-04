"""REQ-P4.2 / P4.3: preview HDR bloom flag and export wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from visualizer.hdr_bloom import (
    ENV_FLAG,
    bloom_params_from_template,
    preview_hdr_bloom_enabled,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", False),
        ("", False),
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("false", False),
    ],
)
def test_preview_hdr_bloom_enabled_flag(value: str, expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_FLAG, value)
    assert preview_hdr_bloom_enabled() is expected


def test_preview_hdr_bloom_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_FLAG, raising=False)
    assert preview_hdr_bloom_enabled() is False


def test_bloom_params_from_template_defaults() -> None:
    strength, threshold, exposure = bloom_params_from_template({})
    assert 0.0 < strength <= 3.0
    assert 0.0 <= threshold <= 1.0
    assert exposure == 1.05


def test_bloom_params_respects_disabled_template_bloom() -> None:
    strength, _, _ = bloom_params_from_template(
        {"effects": {"bloom": {"enabled": False, "strength": 2.0, "opacity": 1.0}}}
    )
    assert strength <= 0.45


def test_preview_widget_wires_hdr_bloom_path() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "preview_widget.py"
    text = src.read_text(encoding="utf-8")
    assert "PreviewHdrBloomPass" in text
    assert "preview_hdr_bloom_enabled" in text
    assert "self._hdr_bloom_frame_active" in text
    assert "hdr.begin_scene" in text
    assert "self._hdr_bloom.resolve" in text
    assert 'not bool(getattr(self, "_interactive_scrub", False))' in text


def test_export_uses_shared_compose_helper() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "gpu_render.py"
    text = src.read_text(encoding="utf-8")
    assert "def _compose_scene_post_to_out" in text
    assert "_compose_scene_post_to_out(" in text
    assert "preview_hdr_bloom_enabled" in text
    assert "hdr_bloom_pass" in text


def test_tonemap_shader_forces_opaque_alpha() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "hdr_bloom.py"
    text = src.read_text(encoding="utf-8")
    assert "frag = vec4(clamp(sdr, 0.0, 1.0), 1.0);" in text
    assert ENV_FLAG in text
    assert "def bloom_params_from_template" in text
