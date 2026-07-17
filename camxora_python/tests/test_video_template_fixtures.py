"""Golden fixture validation for Video TemplateNormalizer (Phase 9d)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "video"

FIXTURE_SETS = ("01", "02", "03", "04")


def _load(name: str) -> object:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _saved_template_name(set_id: str) -> str:
    if set_id == "03":
        return "03_legacy_sensitivity_template.json"
    return f"{set_id}_saved_template.json"


@pytest.mark.parametrize("set_id", FIXTURE_SETS)
def test_fixture_files_exist_and_parse(set_id: str) -> None:
    assert FIXTURES_DIR.is_dir()
    for suffix in ("draft_flat", "layers", "workspace", "expected_renderer_dict"):
        path = FIXTURES_DIR / f"{set_id}_{suffix}.json"
        assert path.is_file(), f"missing {path.name}"
        json.loads(path.read_text(encoding="utf-8"))
    saved = FIXTURES_DIR / _saved_template_name(set_id)
    assert saved.is_file()
    json.loads(saved.read_text(encoding="utf-8"))


@pytest.mark.parametrize("set_id", FIXTURE_SETS)
def test_expected_renderer_dict_has_gpu_audio_alias(set_id: str) -> None:
    expected = _load(f"{set_id}_expected_renderer_dict.json")
    assert isinstance(expected, dict)
    audio = expected.get("audioSettings")
    assert isinstance(audio, dict)
    if "inputGain" in audio:
        assert audio.get("sensitivity") == audio.get("inputGain")


@pytest.mark.parametrize("set_id", FIXTURE_SETS)
def test_expected_text_overlays_use_size_px(set_id: str) -> None:
    expected = _load(f"{set_id}_expected_renderer_dict.json")
    assert isinstance(expected, dict)
    overlays = expected.get("textOverlays", [])
    if not overlays:
        return
    assert isinstance(overlays, list)
    for overlay in overlays:
        assert isinstance(overlay, dict)
        if "fontSize" in overlay:
            pytest.fail("renderer dict must not contain fontSize; use sizePx")
        if overlay.get("enabled") and overlay.get("text"):
            assert "sizePx" in overlay


@pytest.mark.parametrize("set_id", FIXTURE_SETS)
def test_template_normalizer_matches_golden_fixtures(set_id: str) -> None:
    from features.video.services.template_normalizer import TemplateNormalizer

    normalizer = TemplateNormalizer()
    result = normalizer.to_renderer_dict(
        base=_load(_saved_template_name(set_id)),
        draft=_load(f"{set_id}_draft_flat.json"),
        layers=_load(f"{set_id}_layers.json"),
        workspace=_load(f"{set_id}_workspace.json"),
    )
    expected = _load(f"{set_id}_expected_renderer_dict.json")
    assert result == expected
