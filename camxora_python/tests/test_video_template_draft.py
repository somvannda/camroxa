"""Tests for video template draft + save patch."""

from __future__ import annotations

import json
from pathlib import Path

from features.video.lib.video_template_draft import build_video_template_draft
from features.video.lib.video_template_save import build_video_workspace_template_save_patch

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "video"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_build_video_template_draft_matches_fixture_01_defaults() -> None:
    saved = _load("01_saved_template.json")
    draft = build_video_template_draft(saved, logo_path="")
    expected = _load("01_draft_flat.json")
    assert draft["style"] == expected["style"]
    assert draft["audioInputGain"] == expected["audioInputGain"]
    assert draft["backgroundEnabled"] == expected["backgroundEnabled"]


def test_save_patch_includes_renderer_audio_keys_for_fixture_01() -> None:
    saved = _load("01_saved_template.json")
    draft = _load("01_draft_flat.json")
    layers = _load("01_layers.json")
    patch = build_video_workspace_template_save_patch(
        template=saved,
        draft=draft,
        template_name="Minimal Template",
        layers=layers,
    )
    assert patch["templateName"] == "Minimal Template"
    assert patch["audioSettings"]["inputGain"] == 1
    assert patch["textOverlays"] == []
