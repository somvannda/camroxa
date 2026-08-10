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
from visualizer_studio.composition_renderer import document_to_renderer_dict
from visualizer_studio.presets import (
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
        "text",
        "overlay",
        "particles",
        "lighting",
        "camera",
        "post",
        "audio_mapping",
    ]
    assert "logo" not in keys


def test_spectrum_center_image_patch_sets_path_and_attach() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "circle",
            "logoPath": "C:/tmp/center.png",
            "logoEnabled": True,
            "spectrumAttachToLogo": True,
            "compositionLogoSize": 220.0,
            "compositionLogoFitToShape": True,
            "compositionLogoMaskShape": "hexagon",
        },
    )
    assert doc["assets"]["logo"] == "C:/tmp/center.png"
    assert doc["composition"]["logo"]["enabled"] is True
    assert doc["spectrumAttachToLogo"] is True
    assert float(doc["composition"]["logo"]["size"]) == 220.0
    assert doc["composition"]["logo"]["fitToShape"] is True
    assert doc["composition"]["logo"]["maskShape"] == "hexagon"
    cleared = apply_axis_patch(
        doc,
        {"logoPath": "", "logoEnabled": False, "spectrumAttachToLogo": False},
    )
    assert cleared["assets"]["logo"] in (None, "")
    assert cleared["composition"]["logo"]["enabled"] is False
    assert cleared["spectrumAttachToLogo"] is False


def test_composition_shape_radius_independent_of_logo_size() -> None:
    from visualizer_studio.gpu_render import _composition_spectrum_base_radius_px

    tpl = {
        "composition": {
            "spectrum": {"sizeScale": 1.0, "fitRadiusToCenterImage": False},
        }
    }
    r_small_logo = _composition_spectrum_base_radius_px(
        tpl,
        frame_w=1920,
        frame_h=1080,
        sf=1.0,
        logo_visual_radius=50.0,
        attached_to_logo=True,
    )
    r_big_logo = _composition_spectrum_base_radius_px(
        tpl,
        frame_w=1920,
        frame_h=1080,
        sf=1.0,
        logo_visual_radius=400.0,
        attached_to_logo=True,
    )
    assert abs(r_small_logo - r_big_logo) < 1e-6
    tpl2 = {
        "composition": {
            "spectrum": {"sizeScale": 2.0, "fitRadiusToCenterImage": False},
        }
    }
    r_large_shape = _composition_spectrum_base_radius_px(
        tpl2,
        frame_w=1920,
        frame_h=1080,
        sf=1.0,
        logo_visual_radius=50.0,
        attached_to_logo=True,
    )
    assert r_large_shape > r_small_logo * 1.5


def test_logo_contain_in_shape_clamp() -> None:
    from visualizer_studio.gpu_render import (
        _clamp_logo_size_inside_shape,
        _composition_spectrum_base_radius_px,
        _logo_contain_in_shape_enabled,
    )

    assert _clamp_logo_size_inside_shape(500.0, 100.0, contain=False) == 500.0
    clamped = _clamp_logo_size_inside_shape(500.0, 100.0, contain=True)
    assert abs(clamped - 200.0) < 1e-6  # fills to path edge (2 * radius)
    assert _clamp_logo_size_inside_shape(150.0, 100.0, contain=True) == 150.0

    doc = apply_axis_patch(
        blank_studio_document(),
        {"compositionLogoContainInShape": False, "compositionLogoSize": 400.0},
    )
    assert doc["composition"]["logo"]["containInShape"] is False
    assert float(doc["composition"]["logo"]["size"]) == 400.0
    flat = inspector_bind_state(doc)
    assert flat.get("compositionLogoContainInShape") is False

    locked = apply_axis_patch(doc, {"compositionLogoContainInShape": True})
    assert locked["composition"]["logo"]["containInShape"] is True
    assert locked.get("spectrumAttachToLogo") is True
    assert float(locked["composition"]["logo"].get("offsetX") or 0.0) == 0.0
    assert _logo_contain_in_shape_enabled(
        {"composition": locked["composition"], "logoSettings": {"containInShape": True}}
    )

    shape_r = _composition_spectrum_base_radius_px(
        {"composition": locked["composition"]},
        frame_w=1920,
        frame_h=1080,
        sf=1.0,
        logo_visual_radius=0.0,
        attached_to_logo=False,
    )
    max_side = shape_r * 2.0
    assert abs(_clamp_logo_size_inside_shape(max_side + 80.0, shape_r, contain=True) - max_side) < 1e-6
    assert abs(_clamp_logo_size_inside_shape(max_side - 20.0, shape_r, contain=True) - (max_side - 20.0)) < 1e-6


def test_spectrum_layer_raise_angle_patch() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "diamond",
            "compositionSpectrumLayerPatch": {"raiseAngleDeg": 45.0},
        },
    )
    layers = doc["composition"]["spectrum"]["layers"]
    assert layers
    assert abs(float(layers[0].get("raiseAngleDeg")) - 45.0) < 1e-6
    cleared = apply_axis_patch(
        doc,
        {"compositionSpectrumLayerPatch": {"raiseAngleDeg": None, "gravity": "outward"}},
    )
    assert cleared["composition"]["spectrum"]["layers"][0].get("raiseAngleDeg") is None
    assert cleared["composition"]["spectrum"]["layers"][0].get("gravity") == "outward"


def test_spectrum_layer_path_phase_and_bar_overrides_patch() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "triangle",
            "compositionSpectrumLayerPatch": {
                "frequencyScroll": 0.35,
                "barHeightOverrides": {"2": 1.5, "4": 0.6},
            },
        },
    )
    layer = doc["composition"]["spectrum"]["layers"][0]
    assert abs(float(layer.get("frequencyScroll") or 0.0) - 0.35) < 1e-6
    overrides = layer.get("barHeightOverrides") or {}
    assert abs(float(overrides.get("2")) - 1.5) < 1e-6
    from visualizer_studio.composition_renderer import document_to_renderer_dict

    rendered = document_to_renderer_dict(doc)
    rings = rendered.get("layers") or []
    assert rings
    assert abs(float(rings[0].get("frequencyScroll") or 0.0) - 0.35) < 1e-6
    assert abs(float((rings[0].get("barHeightOverrides") or {}).get("2")) - 1.5) < 1e-6


def test_spectrum_shape_rotation_dial_patch() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "triangle",
            "compositionSpectrumRotationDeg": 90.0,
        },
    )
    assert float(doc["composition"]["spectrum"]["rotationDeg"]) == 90.0
    from visualizer_studio.composition_renderer import document_to_renderer_dict

    rendered = document_to_renderer_dict(doc)
    layers = rendered.get("layers") or []
    assert layers
    assert abs(float(layers[0].get("rotation") or 0.0) - 90.0) < 1e-6
    assert abs(float((rendered.get("logoSettings") or {}).get("maskRotationDeg") or 0.0) - 90.0) < 1e-6
    assert abs(float((rendered.get("logoSettings") or {}).get("rotationDeg") or 0.0)) < 1e-6


def test_logo_image_rotation_independent_of_shape() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "diamond",
            "compositionSpectrumRotationDeg": 45.0,
            "compositionLogoRotationDeg": 90.0,
        },
    )
    assert float(doc["composition"]["spectrum"]["rotationDeg"]) == 45.0
    assert float(doc["composition"]["logo"]["rotationDeg"]) == 90.0
    from visualizer_studio.composition_renderer import document_to_renderer_dict

    rendered = document_to_renderer_dict(doc)
    ls = rendered.get("logoSettings") or {}
    assert abs(float(ls.get("maskRotationDeg") or 0.0) - 45.0) < 1e-6
    assert abs(float(ls.get("rotationDeg") or 0.0) - 90.0) < 1e-6


def test_stay_inside_shape_keeps_image_rotation_independent() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "triangle",
            "compositionSpectrumRotationDeg": 183.0,
            "compositionLogoRotationDeg": 12.0,
            "compositionLogoContainInShape": True,
        },
    )
    from visualizer_studio.composition_renderer import document_to_renderer_dict

    rendered = document_to_renderer_dict(doc)
    ls = rendered.get("logoSettings") or {}
    assert bool(ls.get("containInShape")) is True
    assert abs(float(ls.get("maskRotationDeg") or 0.0) - 183.0) < 1e-6
    # Picture must NOT follow Shape rotation — only the crop/mask does.
    assert abs(float(ls.get("rotationDeg") or 0.0) - 12.0) < 1e-6


def test_logo_mask_rotation_uniform_matches_spectrum_convention() -> None:
    """Mask radians must match spectrum rotate_spectrum_bases (no Y flip)."""
    from visualizer_studio.logo_mask import apply_logo_rotation_uniforms

    class _U:
        def __init__(self) -> None:
            self.value = 0.0

    class _Prog(dict):
        pass

    prog_map = _Prog()
    prog_map["logo_rot_rad"] = _U()
    prog_map["logo_mask_rot_rad"] = _U()
    apply_logo_rotation_uniforms(prog_map, content_deg=90.0, mask_deg=90.0)
    assert abs(float(prog_map["logo_mask_rot_rad"].value) - 1.57079632679) < 1e-5
    assert abs(float(prog_map["logo_rot_rad"].value) - 1.57079632679) < 1e-5


def test_logo_mask_mode_follows_spectrum_shape() -> None:
    from visualizer_studio.logo_mask import (
        LOGO_MASK_CIRCLE,
        LOGO_MASK_DIAMOND,
        LOGO_MASK_HEART,
        LOGO_MASK_HEXAGON,
        LOGO_MASK_NONE,
        LOGO_MASK_TRIANGLE,
        resolve_logo_mask_mode,
    )

    assert resolve_logo_mask_mode("triangle", fit_to_shape=True) == LOGO_MASK_TRIANGLE
    assert resolve_logo_mask_mode("hexagon", fit_to_shape=True) == LOGO_MASK_HEXAGON
    assert resolve_logo_mask_mode("diamond", fit_to_shape=True) == LOGO_MASK_DIAMOND
    assert resolve_logo_mask_mode("heart", fit_to_shape=True) == LOGO_MASK_HEART
    assert resolve_logo_mask_mode("ring", fit_to_shape=True) == LOGO_MASK_CIRCLE
    assert resolve_logo_mask_mode("audio_ribbon", fit_to_shape=True) == LOGO_MASK_CIRCLE
    assert resolve_logo_mask_mode("bars", fit_to_shape=True) == LOGO_MASK_NONE
    assert resolve_logo_mask_mode("triangle", fit_to_shape=False, circle_mask=True) == LOGO_MASK_CIRCLE
    assert resolve_logo_mask_mode("triangle", fit_to_shape=False, circle_mask=False) == LOGO_MASK_NONE
    assert resolve_logo_mask_mode("bars", mask_shape="triangle") == LOGO_MASK_TRIANGLE
    assert resolve_logo_mask_mode("heart", mask_shape="square") == LOGO_MASK_NONE
    assert resolve_logo_mask_mode("bars", mask_shape="hexagon") == LOGO_MASK_HEXAGON
    assert resolve_logo_mask_mode(None, mask_shape="circle") == LOGO_MASK_CIRCLE


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
    assert rendered.get("style") == "orbit-spikes"


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
    from visualizer_studio.composition_renderer import document_to_renderer_dict

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
    assert rendered["atmosphereDraw"]["atmosphereId"] == "fog"
    assert rendered["atmosphereDraw"]["kind"] == "volume"


def test_atmosphere_weather_draw_descriptor() -> None:
    from visualizer_studio.composition_effects.atmosphere_gpu import (
        atmosphere_weather_segments,
        build_atmosphere_draw,
    )
    from visualizer_studio.composition_renderer import document_to_renderer_dict

    doc = apply_axis_patch(
        blank_studio_document(),
        {"compositionBackgroundAtmosphere": "rain"},
    )
    rendered = document_to_renderer_dict(doc)
    draw = rendered["atmosphereDraw"]
    assert draw["kind"] == "weather"
    assert build_atmosphere_draw(rendered["atmosphereSettings"]) is not None
    segs = atmosphere_weather_segments(
        kind="rain",
        density=0.6,
        speed=1.0,
        tint="#dbeafe",
        time_sec=1.25,
        width=1280,
        height=720,
    )
    assert segs.shape[0] >= 40
    assert segs.shape[1] == 6


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
