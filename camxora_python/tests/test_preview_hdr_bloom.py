"""REQ-P4.2: preview HDR bloom flag and paintGL wiring."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from visualizer.hdr_bloom import ENV_FLAG, preview_hdr_bloom_enabled


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


def test_preview_widget_wires_hdr_bloom_path() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "preview_widget.py"
    text = src.read_text(encoding="utf-8")
    assert "from visualizer.hdr_bloom import PreviewHdrBloomPass, preview_hdr_bloom_enabled" in text
    assert "self._hdr_bloom_frame_active" in text
    assert "hdr.begin_scene" in text
    assert "self._hdr_bloom.resolve" in text
    assert "_interactive_scrub" in text
    assert 'not bool(getattr(self, "_interactive_scrub", False))' in text


def test_tonemap_shader_forces_opaque_alpha() -> None:
    src = Path(__file__).resolve().parents[1] / "visualizer" / "hdr_bloom.py"
    text = src.read_text(encoding="utf-8")
    assert "frag = vec4(clamp(sdr, 0.0, 1.0), 1.0);" in text
    assert ENV_FLAG in text
