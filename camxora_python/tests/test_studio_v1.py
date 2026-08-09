"""Composition Studio v1 — store, axes, compile smoke (independent of Video)."""

from __future__ import annotations

from pathlib import Path

import pytest

from features.studio.lib.scene_document import (
    SCENE_TREE_NODES,
    apply_axis_patch,
    blank_studio_document,
    inspector_bind_state,
    normalize_studio_document,
)
from features.studio.lib.schema_bridge import composition_to_project, project_to_composition
from features.studio.services.studio_export import (
    build_studio_manual_export_request,
    export_project_json,
    studio_export_readiness,
)
from features.studio.services.studio_store import StudioStore
from visualizer.composition_renderer import document_to_renderer_dict
from visualizer.presets import (
    ATMOSPHERE_COUNT,
    AUDIO_BUS_COUNT,
    BACKGROUND_MOTION_COUNT,
    CAMERA_BEHAVIOR_COUNT,
    LIGHTING_EFFECT_COUNT,
    POST_EFFECT_COUNT,
    all_asset_metadata,
    get_asset_metadata,
    search_assets,
)


def test_scene_tree_has_architecture_nodes() -> None:
    keys = [k for k, _ in SCENE_TREE_NODES]
    assert keys == [
        "palette",
        "background",
        "spectrum",
        "logo",
        "text",
        "overlay",
        "particles",
        "lighting",
        "camera",
        "post",
        "audio_mapping",
    ]


def test_blank_document_compiles() -> None:
    doc = blank_studio_document(name="Smoke")
    doc = apply_axis_patch(
        doc,
        {
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "neon",
            "compositionSpectrumAnimation": "pulse",
            "compositionColorPalette": "cyberpunk",
            "compositionLightingEffect": "lightning",
            "compositionLightingTrigger": "bass",
            "compositionCameraBehavior": "shake",
            "compositionBackgroundMotion": "ken_burns",
            "compositionBackgroundAtmosphere": "fog",
            "compositionPostEffects": ["bloom", "vignette"],
            "compositionAudioMapping": {
                "lighting": "bass",
                "particles": "kick",
                "camera": "bass",
                "logo": "vocals",
            },
        },
    )
    rendered = document_to_renderer_dict(doc)
    assert rendered["engine"]["compiled"] is True
    assert rendered["engine"]["spectrum"]["shape"] == "circle"
    assert rendered["engine"]["lighting"] == "lightning"
    assert "style" not in rendered


def test_catalog_counts_available() -> None:
    assert LIGHTING_EFFECT_COUNT == 15
    assert CAMERA_BEHAVIOR_COUNT == 15
    assert ATMOSPHERE_COUNT == 15
    assert BACKGROUND_MOTION_COUNT == 10
    assert POST_EFFECT_COUNT == 20
    assert AUDIO_BUS_COUNT == 8


def test_studio_store_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "features.studio.services.studio_store.get_studio_projects_dir",
        lambda _user_id=None: tmp_path / "projects",
    )
    monkeypatch.setattr(
        "features.studio.services.studio_store.get_studio_prefs_path",
        lambda _user_id=None: tmp_path / "prefs.json",
    )
    store = StudioStore()
    created = store.create_project(name="Demo")
    assert created["id"]
    loaded = store.load_project(created["id"])
    assert loaded is not None
    assert loaded["name"] == "Demo"
    listed = store.list_projects()
    assert any(pid == created["id"] for pid, _name in listed)


def test_inspector_bind_state_keys() -> None:
    state = inspector_bind_state(blank_studio_document())
    assert "compositionSpectrumShape" in state
    assert "compositionAudioMapping" in state


def test_normalize_preserves_name() -> None:
    doc = normalize_studio_document({"name": "Neon Night", "composition": {"spectrum": {"shape": "bars"}}})
    assert doc["name"] == "Neon Night"
    assert doc["composition"]["spectrum"]["shape"] == "bars"


def test_asset_metadata_search_and_overrides() -> None:
    assert len(all_asset_metadata()) > 50
    neon = get_asset_metadata("neon", category="material")
    assert neon is not None
    assert "EDM" in neon.genre
    hits = search_assets(query="cyberpunk", category="palette")
    assert any(item.id == "cyberpunk" for item in hits)


def test_schema_bridge_roundtrip_preserves_axes() -> None:
    doc = apply_axis_patch(
        blank_studio_document(name="Bridge"),
        {
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "neon",
            "compositionLightingEffect": "lightning",
            "compositionPostEffects": ["bloom"],
            "compositionColorPalette": "cyberpunk",
        },
    )
    project = composition_to_project(doc)
    assert project["schema"] == "camxora.project"
    assert project["scenes"][0]["objects"]
    restored = project_to_composition(project)
    assert restored["composition"]["spectrum"]["shape"] == "circle"
    assert restored["composition"]["spectrum"]["material"] == "neon"
    assert restored["composition"]["lighting"]["effect"] == "lightning"
    assert restored["composition"]["postProcessing"]["effects"] == ["bloom"]
    assert restored["composition"]["colorPalette"] == "cyberpunk"


def test_post_effects_append_and_audio_path_patch() -> None:
    doc = blank_studio_document()
    doc = apply_axis_patch(doc, {"compositionPostEffectsAppend": "bloom"})
    doc = apply_axis_patch(doc, {"compositionPostEffectsAppend": "vignette"})
    doc = apply_axis_patch(doc, {"audioPath": r"C:\tmp\track.mp3"})
    assert doc["composition"]["postProcessing"]["effects"] == ["bloom", "vignette"]
    assert doc["assets"]["audio"] == r"C:\tmp\track.mp3"


def test_normalize_preserves_studio_extras() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "spectrumAttachToLogo": True,
            "albumEnabled": True,
            "albumManualText": "Neon Nights",
            "logoPath": r"C:\tmp\logo.png",
        },
    )
    # A different axis patch must not wipe Studio extras.
    doc = apply_axis_patch(doc, {"compositionSpectrumShape": "circle"})
    assert doc["spectrumAttachToLogo"] is True
    assert doc["albumEnabled"] is True
    assert doc["albumManualText"] == "Neon Nights"
    assert doc["assets"]["logo"] == r"C:\tmp\logo.png"


def test_gpu_bridge_wires_lighting_camera_atmosphere() -> None:
    from visualizer.composition_renderer import document_to_renderer_dict

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "circle",
            "compositionLightingEffect": "lightning",
            "compositionLightingTrigger": "bass",
            "compositionCameraBehavior": "shake",
            "compositionBackgroundAtmosphere": "fog",
            "compositionBackgroundMotion": "ken_burns",
            "compositionPostEffects": ["bloom"],
        },
    )
    rendered = document_to_renderer_dict(doc, time_sec=1.0, audio_level=0.8)
    assert rendered["lightningEnabled"] is True
    assert rendered["lightningLayers"]
    assert rendered["effects"]["camera_shake"]["enabled"] is True
    assert rendered["backgroundSettings"]["motionMode"] in {"zoom", "vibrate", "both"}
    assert rendered["effects"]["soft_diffusion"]["enabled"] is True
    assert "bloom" in rendered["effects"]


def test_studio_export_readiness_and_json(tmp_path: Path) -> None:
    audio = tmp_path / "a.mp3"
    bg = tmp_path / "bg.png"
    audio.write_bytes(b"x")
    bg.write_bytes(b"y")
    doc = blank_studio_document(name="Export Me")
    ok, reason = studio_export_readiness(doc)
    assert ok is False
    assert "audio" in reason.lower()
    doc = apply_axis_patch(
        doc,
        {
            "audioPath": str(audio),
            "backgroundImage": str(bg),
            "compositionSpectrumShape": "circle",
        },
    )
    ok, reason = studio_export_readiness(doc)
    assert ok is True
    assert reason == ""
    out = export_project_json(doc, tmp_path / "export.project.json")
    assert out.is_file()
    request = build_studio_manual_export_request(doc, output_dir=str(tmp_path))
    assert request.mode == "manual"
    assert request.context.branch == "studio"
    assert request.assets.audio_path == str(audio)
    assert request.template.get("schema") == "camxora.composition"
