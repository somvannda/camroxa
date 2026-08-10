"""P1–P7 Studio platform phase smoke tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from features.studio.lib.scene_document import apply_axis_patch, blank_studio_document
from features.studio.lib.schema_validate import validate_composition_document, validate_project_document
from features.studio.plugins.loader import discover_plugins, plugin_catalog_entries
from features.studio.services.ai_designer import AiDesignerEngine
from features.studio.services.marketplace_cloud import MarketplaceCloudService
from features.studio.services.template_library import StudioTemplateLibrary
from features.studio.lib.schema_bridge import composition_to_project
from visualizer_studio.composition_effects.camera_gpu import camera_view_offset_px
from visualizer_studio.composition_renderer import document_to_renderer_dict


def test_p1_camera_and_overlay_bridge() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionCameraBehavior": "orbit",
            "compositionOverlayEnabled": True,
            "overlayStyle": "vhs",
            "albumEnabled": True,
            "albumManualText": "Neon Nights",
            "compositionLightingEffect": "god_rays",
        },
    )
    rendered = document_to_renderer_dict(doc, time_sec=1.5, audio_level=0.7)
    cam = rendered.get("cameraSettings") or {}
    ox, oy, zoom = camera_view_offset_px(cam, width=1920, height=1080)
    assert cam.get("behaviorId") == "orbit"
    assert abs(ox) > 0 or abs(oy) > 0 or zoom != 1.0
    assert rendered["effects"]["rgb_split"]["enabled"] is True
    assert rendered["textOverlays"]
    assert rendered["effects"]["bloom"]["enabled"] is True


def test_p3_template_library_roundtrip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "features.studio.services.template_library.get_studio_templates_dir",
        lambda _user_id=None: tmp_path / "templates",
    )
    lib = StudioTemplateLibrary()
    doc = apply_axis_patch(blank_studio_document(name="Pack"), {"compositionSpectrumShape": "circle"})
    saved = lib.save_template(doc, name="Pack")
    loaded = lib.load_template(str(saved["templateId"]))
    assert loaded is not None
    assert loaded["composition"]["spectrum"]["shape"] == "circle"
    dup = lib.duplicate(str(saved["templateId"]))
    assert dup is not None


def test_p3_schema_validate() -> None:
    doc = blank_studio_document()
    assert validate_composition_document(doc) == []
    project = composition_to_project(doc)
    assert validate_project_document(project) == []
    assert validate_composition_document(None)


def test_p5_ai_designer_generate() -> None:
    engine = AiDesignerEngine()
    result = engine.generate("cyberpunk purple EDM festival lightning")
    assert result.document["composition"]["spectrum"]["material"] in {"neon", "carbon", "glass", "ice"}
    assert result.document["composition"]["lighting"]["effect"]
    assert "Palette=" in result.explanation
    improved = engine.improve(result.document)
    assert improved.mode == "improve"


def test_p6_plugin_discovery() -> None:
    plugins_dir = Path(__file__).resolve().parents[1] / "features" / "studio" / "plugins"
    plugins = discover_plugins(plugins_dir)
    assert any(p.id.endswith("sample-neon-spectrum") for p in plugins)
    entries = plugin_catalog_entries(plugins)
    assert any("neon" in str(e.get("name") or "").lower() or "sample" in str(e.get("id") or "") for e in entries)


def test_p7_marketplace_cloud_stub() -> None:
    svc = MarketplaceCloudService()
    listings = svc.list_marketplace()
    assert listings
    job = svc.enqueue_cloud_render(project_id="abc12345")
    assert job.status == "done"
    assert "roles" in svc.enterprise_roles()


def test_expert_tuning_and_video_plate_bridge() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "circle",
            "compositionSpectrumBarHeight": 1.8,
            "compositionSpectrumGlow": 0.9,
            "compositionCameraPanX": 0.2,
            "compositionCameraZoomBias": 1.2,
            "compositionLightingEffect": "aura",
            "compositionLightingIntensity": 1.1,
            "compositionPostEffects": ["bloom", "vignette"],
            "compositionPostAmount": 0.8,
            "backgroundVideo": "C:/fake/plate.mp4",
        },
    )
    assert doc["composition"]["spectrum"]["barHeight"] == 1.8
    assert doc["assets"]["backgroundVideo"] == "C:/fake/plate.mp4"
    rendered = document_to_renderer_dict(doc, time_sec=0.5, audio_level=0.4)
    assert float(rendered["audioSettings"]["barHeight"]) == 1.8
    assert float(rendered["cameraSettings"]["panX"]) == 0.2
    assert float(rendered["cameraSettings"]["zoomBias"]) == 1.2
    assert rendered.get("backgroundVideo") == "C:/fake/plate.mp4"
    assert rendered["effects"]["bloom"]["enabled"] is True


def test_video_path_helper() -> None:
    from visualizer_studio.composition_effects.video_background import is_video_path

    assert is_video_path("clip.mp4")
    assert is_video_path("plate.MOV")
    assert not is_video_path("still.png")


def test_rest_scene_axes_compile_wired() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "logoPath": "C:/fake/logo.png",
            "compositionLogoAnimation": "rotate",
            "compositionTextEnabled": True,
            "albumEnabled": True,
            "albumManualText": "Wired",
            "compositionOverlayEnabled": True,
            "overlayStyle": "vhs",
            "compositionParticleType": "embers",
            "compositionParticleBehavior": "pulse",
            "compositionLightingEffect": "aura",
            "compositionCameraBehavior": "orbit",
            "compositionPostEffects": ["vignette", "film_grain", "bloom"],
            "compositionAudioMapping": {"lighting": "bass", "particles": "kick", "camera": "none", "logo": "vocals"},
        },
    )
    rendered = document_to_renderer_dict(doc, time_sec=1.2, audio_level=0.7)
    assert rendered["logoSettings"]["spinEnabled"] is True
    assert rendered["textOverlays"]
    assert rendered["effects"]["rgb_split"]["enabled"] is True
    assert rendered["particlesSettings"]["enabled"] is True
    assert rendered["particlesSettings"]["typeId"] == "embers"
    assert rendered["particlesSettings"]["color"] != "#ff4fd8"  # type-native, not default palette
    assert rendered["lightningEnabled"] is True
    assert rendered["cameraSettings"]["behaviorId"] == "orbit"
    assert rendered["effects"]["vignette"]["enabled"] is True
    assert rendered["audioMapping"]["mappedLevels"]["lighting"] > 0


def test_spectrum_material_and_animation_stay_distinct() -> None:
    """Expert glow must scale materials, not flatten Chrome/Neon/Matte together."""
    base = {
        "compositionSpectrumShape": "ring",
        "compositionSpectrumBarHeight": 2.75,
        "compositionSpectrumGlow": 0.5,
        "compositionSpectrumAnimation": "pulse",
    }
    chrome = document_to_renderer_dict(
        apply_axis_patch(blank_studio_document(), {**base, "compositionSpectrumMaterial": "chrome"}),
        time_sec=1.0,
        audio_level=0.7,
    )
    matte = document_to_renderer_dict(
        apply_axis_patch(blank_studio_document(), {**base, "compositionSpectrumMaterial": "matte"}),
        time_sec=1.0,
        audio_level=0.7,
    )
    neon = document_to_renderer_dict(
        apply_axis_patch(blank_studio_document(), {**base, "compositionSpectrumMaterial": "neon"}),
        time_sec=1.0,
        audio_level=0.7,
    )
    assert float(chrome["layers"][0]["glow"]) > float(matte["layers"][0]["glow"]) + 5
    assert float(neon["layers"][0]["glow"]) > float(chrome["layers"][0]["glow"])
    assert chrome["layers"][0]["barWidth"] != matte["layers"][0]["barWidth"]
    # Animation multiplies expert bar height (not replaced).
    assert float(chrome["audioSettings"]["barHeight"]) > 2.75


def test_live_motion_updates_camera_over_time() -> None:
    from visualizer_studio.composition_effects.live_motion import apply_live_composition_motion

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionCameraBehavior": "orbit",
            "compositionBackgroundMotion": "ken_burns",
            "compositionAudioMapping": {"camera": "bass", "lighting": "none", "particles": "none", "logo": "none"},
        },
    )
    rendered = document_to_renderer_dict(doc, time_sec=0.0, audio_level=0.2)
    apply_live_composition_motion(rendered, time_sec=0.0, bass=0.2, kick=0.1, beat=0.1)
    a = float(rendered["cameraSettings"]["offsetX"])
    apply_live_composition_motion(rendered, time_sec=1.6, bass=0.9, kick=0.4, beat=0.5)
    b = float(rendered["cameraSettings"]["offsetX"])
    assert a != b
    assert rendered["backgroundSettings"]["motionMode"] in {"zoom", "vibrate", "both", "none"}
    assert abs(float(rendered["backgroundSettings"].get("userOffsetX") or 0.0)) > 0.0


def test_live_motion_syncs_spectrum_animation_into_instances() -> None:
    """Preview paints spectrumInstances layers; live motion must update those copies."""
    from visualizer_studio.composition_effects.live_motion import apply_live_composition_motion
    from visualizer_studio.template_runtime import normalize_renderer_template

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "circle",
            "compositionSpectrumAnimation": "rotate",
            "compositionSpectrumMaterial": "chrome",
        },
    )
    # Mirror preview: compile → normalize (deep-copies layers into spectrumInstances).
    rendered = normalize_renderer_template(document_to_renderer_dict(doc, time_sec=0.0, audio_level=0.5))
    assert rendered.get("spectrumInstances"), "normalize should migrate legacy layers to instances"
    apply_live_composition_motion(rendered, time_sec=1.25, bass=0.6, kick=0.3, beat=0.4)
    top = (rendered.get("layers") or [{}])[0]
    inst = ((rendered.get("spectrumInstances") or [{}])[0].get("layers") or [{}])[0]
    assert float(top.get("rotation") or 0.0) != 0.0
    assert float(inst.get("rotation") or 0.0) == float(top.get("rotation") or 0.0)
    assert float(inst.get("animScale") or 1.0) == float(top.get("animScale") or 1.0)
    assert str(inst.get("animationId") or "") == "rotate"
    assert float((rendered.get("spectrumInstances") or [{}])[0]["audioSettings"]["barHeight"]) == float(
        rendered["audioSettings"]["barHeight"]
    )


def test_rain_atmosphere_falls_downward() -> None:
    """Rain streaks must travel toward -Y in NDC (down), not fly upward."""
    from visualizer_studio.composition_effects.atmosphere_gpu import atmosphere_weather_segments

    a = atmosphere_weather_segments(
        kind="rain", density=0.8, speed=1.4, tint="#bfdbfe", time_sec=0.0, width=1920, height=1080
    )
    b = atmosphere_weather_segments(
        kind="rain", density=0.8, speed=1.4, tint="#bfdbfe", time_sec=0.2, width=1920, height=1080
    )
    # Tip (odd) sits below head (even) in NDC.
    assert float(a[1, 1]) < float(a[0, 1])
    # Particle 0 tip moves downward unless it wrapped this frame.
    dy = float(b[1, 1] - a[1, 1])
    assert dy < 0.0 or abs(dy) > 1.0


def test_atmosphere_styles_have_unique_draw_kinds() -> None:
    from visualizer_studio.composition_effects.atmosphere import build_atmosphere_pass
    from features.studio.lib.scene_document import catalog_options

    kinds: dict[str, str] = {}
    for aid, _ in catalog_options()["atmosphere"]:
        pass_ = build_atmosphere_pass(aid)
        assert pass_ is not None
        kinds[aid] = str((pass_.get("draw") or {}).get("kind"))
    assert kinds["rain"] == "weather"
    assert kinds["fog"] == "volume"
    assert kinds["stars"] == "sky"
    assert kinds["heatwave"] == "distort"
    # Expert density scale must change draw density.
    low = build_atmosphere_pass("rain", density_scale=0.3)
    high = build_atmosphere_pass("rain", density_scale=2.0)
    assert float(high["draw"]["density"]) > float(low["draw"]["density"])
    # Density 0 turns atmosphere off (no stuck wash).
    off = build_atmosphere_pass("rain", density_scale=0.0)
    assert off is not None
    assert off["enabled"] is False
    from visualizer_studio.composition_effects.atmosphere_gpu import (
        atmosphere_weather_segments,
        build_atmosphere_draw,
    )

    assert build_atmosphere_draw(off) is None
    # Low density still draws visible streaks (opacity, not density, sets alpha).
    sparse = atmosphere_weather_segments(
        kind="rain", density=0.25, speed=1.0, tint="#bfdbfe", time_sec=0.0, width=1280, height=720, opacity=1.0
    )
    dense = atmosphere_weather_segments(
        kind="rain", density=1.2, speed=1.0, tint="#bfdbfe", time_sec=0.0, width=1280, height=720, opacity=1.0
    )
    assert 0 < sparse.shape[0] < dense.shape[0]
    assert float(sparse[1, 5]) == float(dense[1, 5])


def test_motion_expert_scales_change_offsets() -> None:
    from visualizer_studio.composition_effects.background_motion import evaluate_background_motion

    mild = evaluate_background_motion("ken_burns", time_sec=1.2, speed=1.0, amplitude=0.5, zoom_amount=0.5)
    wild = evaluate_background_motion("ken_burns", time_sec=1.2, speed=1.0, amplitude=2.5, zoom_amount=2.5)
    assert abs(float(wild["offsetX"])) > abs(float(mild["offsetX"]))
    assert float(wild["scale"]) != float(mild["scale"])


def test_background_motions_have_distinct_live_signatures() -> None:
    from visualizer_studio.composition_effects.live_motion import apply_live_composition_motion

    signatures: dict[str, tuple[float, float, float, str]] = {}
    for motion in ("static", "ken_burns", "floating", "rotate", "warp", "energy_wave"):
        doc = apply_axis_patch(
            blank_studio_document(),
            {"compositionBackgroundMotion": motion},
        )
        rendered = document_to_renderer_dict(doc, time_sec=1.25, audio_level=0.4)
        apply_live_composition_motion(rendered, time_sec=1.25, bass=0.3, kick=0.2, beat=0.2)
        bg = rendered["backgroundSettings"]
        signatures[motion] = (
            round(float(bg.get("userScale") or 1.0), 4),
            round(float(bg.get("userOffsetX") or 0.0), 3),
            round(float(bg.get("userOffsetY") or 0.0), 3),
            str(bg.get("motionMode") or "none"),
        )
    assert signatures["static"][0] == 1.0
    assert signatures["ken_burns"][0] != signatures["floating"][0] or signatures["ken_burns"][1:] != signatures["floating"][1:]
    assert signatures["rotate"] != signatures["floating"]
    assert signatures["warp"] != signatures["ken_burns"]
    assert len(set(signatures.values())) >= 5


def test_spectrum_layers_and_size_scale_compile() -> None:
    from visualizer_studio.composition_renderer import document_to_renderer_dict
    from visualizer_studio.scene.spectrum_layers import normalize_spectrum_layers

    blank = blank_studio_document()
    layers = normalize_spectrum_layers(blank["composition"]["spectrum"].get("layers"))
    assert len(layers) == 1
    assert float(blank["composition"]["spectrum"].get("sizeScale") or 1.0) == 1.0

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "neon",
            "compositionSpectrumSizeScale": 1.8,
            "compositionSpectrumLayerAdd": True,
        },
    )
    rings = doc["composition"]["spectrum"]["layers"]
    assert len(rings) >= 2
    assert float(rings[1]["radiusOffset"]) > float(rings[0]["radiusOffset"])

    rendered = document_to_renderer_dict(doc, time_sec=0.5, audio_level=0.3)
    out_layers = [x for x in (rendered.get("layers") or []) if isinstance(x, dict)]
    assert len(out_layers) >= 2
    assert abs(float(out_layers[0].get("sizeScale") or 1.0) - 1.8) < 1e-6

    moved = apply_axis_patch(
        doc, {"compositionSpectrumPositionPx": {"x": 96.0, "y": -54.0}}
    )
    assert abs(float(moved["composition"]["spectrum"]["offsetX"]) - 0.2) < 1e-6
    assert abs(float(moved["composition"]["spectrum"]["offsetY"]) - (-0.2)) < 1e-6


def test_background_motion_tuning_ui_is_contextual() -> None:
    from visualizer_studio.presets.background_motion import (
        BACKGROUND_MOTION_IDS,
        background_motion_tuning_ui,
    )

    assert background_motion_tuning_ui("static") == {}
    assert set(background_motion_tuning_ui("slow_zoom")) == {"speed", "zoom"}
    ken = background_motion_tuning_ui("ken_burns")
    assert ken["amplitude"] == "Pan strength"
    assert set(ken) == {"speed", "amplitude", "zoom"}
    warp = background_motion_tuning_ui("warp")
    assert set(warp) == {"speed", "amplitude", "zoom", "warp"}
    # Every catalog id has an entry (static may be empty).
    for mid in BACKGROUND_MOTION_IDS:
        assert isinstance(background_motion_tuning_ui(mid), dict)


def test_studio_export_options_wire_into_request() -> None:
    from features.studio.services.studio_export import (
        build_studio_manual_export_request,
        studio_export_options,
        studio_export_readiness,
    )

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "audioPath": "C:/fake/track.mp3",
            "backgroundImage": "C:/fake/bg.png",
            "studioExport": {
                "resolution": "1280x720",
                "fps": 30,
                "quality": "balanced",
                "includeAudio": False,
                "rangeStart": 1.0,
                "rangeEnd": 12.0,
            },
        },
    )
    opts = studio_export_options(doc)
    assert opts["resolution"] == "1280x720"
    assert opts["fps"] == 30
    assert opts["quality"] == "balanced"
    assert opts["includeAudio"] is False
    scene = build_studio_manual_export_request(doc, output_dir="C:/out")
    assert scene.output.resolution == "1280x720"
    assert scene.output.fps == 30
    assert scene.output.width == 1280
    assert scene.template["studioExport"]["rangeEnd"] == 12.0
    # Paths are fake — readiness should fail on missing files, not missing options.
    ok, reason = studio_export_readiness(doc)
    assert ok is False
    assert "missing" in reason.lower() or "select" in reason.lower()


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_shapes_keep_unique_geometry_under_same_material() -> None:
    chrome_circle = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionSpectrumShape": "circle", "compositionSpectrumMaterial": "chrome"},
        ),
        time_sec=1.0,
        audio_level=0.5,
    )
    chrome_ring = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionSpectrumShape": "ring", "compositionSpectrumMaterial": "chrome"},
        ),
        time_sec=1.0,
        audio_level=0.5,
    )
    chrome_wave = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionSpectrumShape": "wave", "compositionSpectrumMaterial": "chrome"},
        ),
        time_sec=1.0,
        audio_level=0.5,
    )
    chrome_bars = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionSpectrumShape": "bars", "compositionSpectrumMaterial": "chrome"},
        ),
        time_sec=1.0,
        audio_level=0.5,
    )
    c0 = chrome_circle["layers"][0]
    r0 = chrome_ring["layers"][0]
    w0 = chrome_wave["layers"][0]
    b0 = chrome_bars["layers"][0]
    assert (c0["barWidth"], c0["thickness"], c0.get("radiusOffset")) != (
        r0["barWidth"],
        r0["thickness"],
        r0.get("radiusOffset"),
    )
    assert (w0.get("gravity"), w0.get("mirrored"), w0["barWidth"]) != (
        b0.get("gravity"),
        b0.get("mirrored"),
        b0["barWidth"],
    )


def test_lighting_effects_have_unique_layer_profiles() -> None:
    sigs = {}
    for effect in ("aura", "neon_rim", "glow", "halo", "god_rays", "volumetric_shaft", "lightning"):
        rendered = document_to_renderer_dict(
            apply_axis_patch(
                blank_studio_document(),
                {"compositionLightingEffect": effect, "compositionLightingTrigger": "bass"},
            ),
            time_sec=1.0,
            audio_level=0.6,
        )
        layer = (rendered.get("lightningLayers") or [{}])[0]
        sigs[effect] = (
            layer.get("style"),
            round(float(layer.get("thickness") or 0), 2),
            round(float(layer.get("glow") or 0), 2),
            round(float(layer.get("length") or 0), 1),
            layer.get("effectId"),
        )
    assert len(set(sigs.values())) == len(sigs)


def test_overlay_dust_differs_from_film_grain() -> None:
    grain = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionOverlayEnabled": True, "overlayStyle": "film_grain"},
        )
    )
    dust = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {"compositionOverlayEnabled": True, "overlayStyle": "dust"},
        )
    )
    assert grain["effects"].get("film_grain", {}).get("enabled")
    assert dust["effects"].get("soft_diffusion", {}).get("enabled")
    assert grain["overlaySettings"]["style"] != dust["overlaySettings"]["style"]


def test_live_motion_retints_palette_on_instances() -> None:
    """Palette must win on spectrumInstances even after normalize deep-copy."""
    from visualizer_studio.composition_effects.live_motion import apply_live_composition_motion
    from visualizer_studio.template_runtime import normalize_renderer_template

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionColorPalette": "ocean",
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "neon",
        },
    )
    rendered = normalize_renderer_template(document_to_renderer_dict(doc, time_sec=0.2, audio_level=0.3))
    # Poison instance colors as if a stale copy survived.
    rendered["spectrumInstances"][0]["layers"][0]["color"] = {
        "mode": "solid",
        "solidColor": "#111111",
        "gradientColors": ["#111111", "#222222"],
    }
    apply_live_composition_motion(rendered, time_sec=0.5, bass=0.4, kick=0.2, beat=0.2)
    inst_color = rendered["spectrumInstances"][0]["layers"][0]["color"]
    assert inst_color["solidColor"] == "#0090ff"
    assert "#0090ff" in (inst_color.get("gradientColors") or [])
    assert rendered.get("paletteSettings", {}).get("paletteId") == "ocean"


def test_palette_expert_tunes_layer_colors() -> None:
    base = {"compositionColorPalette": "ocean", "compositionSpectrumShape": "bars"}
    plain = document_to_renderer_dict(apply_axis_patch(blank_studio_document(), base))
    vivid = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {**base, "compositionPaletteIntensity": 1.8, "compositionPaletteSaturation": 1.7},
        )
    )
    muted = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {**base, "compositionPaletteIntensity": 0.35, "compositionPaletteSaturation": 0.4},
        )
    )
    plain_stops = tuple((plain["layers"][0]["color"] or {}).get("gradientColors") or [])
    vivid_stops = tuple((vivid["layers"][0]["color"] or {}).get("gradientColors") or [])
    muted_stops = tuple((muted["layers"][0]["color"] or {}).get("gradientColors") or [])
    assert plain_stops and vivid_stops and muted_stops
    assert vivid_stops != plain_stops
    assert muted_stops != plain_stops
    assert vivid.get("paletteSettings", {}).get("intensity") == 1.8


def test_spectrum_local_palette_overrides_global() -> None:
    global_only = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {
                "compositionColorPalette": "ocean",
                "compositionSpectrumShape": "circle",
                "compositionSpectrumMaterial": "neon",
            },
        )
    )
    local = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {
                "compositionColorPalette": "ocean",
                "compositionSpectrumColorPalette": "sunset",
                "compositionSpectrumShape": "circle",
                "compositionSpectrumMaterial": "neon",
            },
        )
    )
    g_solid = str((global_only["layers"][0]["color"] or {}).get("solidColor") or "").lower()
    l_solid = str((local["layers"][0]["color"] or {}).get("solidColor") or "").lower()
    assert g_solid.startswith("#")
    assert l_solid.startswith("#")
    assert l_solid != g_solid


def test_spectrum_bar_controls_reach_layers() -> None:
    rendered = document_to_renderer_dict(
        apply_axis_patch(
            blank_studio_document(),
            {
                "compositionSpectrumShape": "circle",
                "compositionSpectrumBarCount": 96,
                "compositionSpectrumPeakCaps": True,
                "compositionSpectrumSolidBand": True,
                "compositionSpectrumMirrored": True,
                "compositionSpectrumTipTaper": 0.8,
                "compositionPerformanceQuality": "medium",
            },
        )
    )
    layer = rendered["layers"][0]
    assert int(layer["barCount"]) == 96
    assert bool(layer.get("peakCapsEnabled")) is True
    assert bool(layer.get("solidBand")) is True
    assert bool(layer.get("mirrored")) is True
    assert float(layer.get("tipTaper") or 0.0) == 0.8


def test_layer_audio_bus_shapes_fft_bins() -> None:
    from visualizer_studio.composition_effects.bus_fft import apply_layer_audio_bus, bus_bin_weights

    n = 64
    flat = np.ones(n, dtype=np.float32)
    bass_w = bus_bin_weights(n, "bass")
    treble_w = bus_bin_weights(n, "treble")
    assert float(bass_w[0]) > float(bass_w[-1])
    assert float(treble_w[-1]) > float(treble_w[0])
    levels = {"bass": 1.0, "treble": 0.05}
    bass_fft = apply_layer_audio_bus(flat, bus_id="bass", bus_levels=levels, audio_gain=1.0)
    treble_fft = apply_layer_audio_bus(flat, bus_id="treble", bus_levels=levels, audio_gain=1.0)
    assert float(bass_fft[0]) > float(treble_fft[0])
    assert float(np.mean(bass_fft)) > float(np.mean(treble_fft))


def test_spectrum_raise_and_solid_graph_patch() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "ring",
            "compositionSpectrumLayerPatch": {
                "gravity": "outward",
                "solidBand": True,
                "barWidthScale": 0.3,
                "name": "Bass ring",
            },
            "spectrumAttachToLogo": True,
            "compositionSpectrumAnimation": "pulse",
            "compositionSpectrumAnimationScale": 1.5,
            "compositionSpectrumAnimationKick": 1.2,
        },
    )
    layer0 = doc["composition"]["spectrum"]["layers"][0]
    assert layer0.get("gravity") == "outward"
    assert bool(layer0.get("solidBand")) is True
    assert layer0.get("name") == "Bass ring"
    assert float(layer0.get("barWidthScale") or 0.0) == 0.3
    assert float(doc["composition"]["spectrum"].get("animationScaleAmount") or 0.0) == 1.5
    assert bool(doc.get("spectrumAttachToLogo")) is True
    rendered = document_to_renderer_dict(doc, time_sec=0.0, audio_level=0.5)
    assert rendered["layers"][0].get("gravity") == "outward"
    assert bool(rendered["layers"][0].get("solidBand")) is True
    assert float(rendered["layers"][0].get("barWidth") or 99.0) < 4.0


def test_soft_eq_shape_and_animation_speed() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "soft_eq",
            "compositionSpectrumMaterial": "matte",
            "compositionSpectrumAnimation": "pulse",
            "compositionSpectrumAnimationSpeed": 2.0,
            "compositionSpectrumBarWidthScale": 0.2,
            "compositionSpectrumLayerPatch": {"audioBus": "bass", "audioGain": 1.5},
        },
    )
    assert doc["composition"]["spectrum"]["shape"] == "soft_eq"
    assert float(doc["composition"]["spectrum"]["animationSpeed"]) == 2.0
    assert float(doc["composition"]["spectrum"]["barWidthScale"]) == 0.2
    layer0 = doc["composition"]["spectrum"]["layers"][0]
    assert layer0.get("audioBus") == "bass"
    assert float(layer0.get("audioGain") or 0.0) == 1.5
    rendered = document_to_renderer_dict(doc, time_sec=0.5, audio_level=0.4)
    assert float(rendered["layers"][0].get("barWidth") or 0.0) < 2.0
    assert bool(rendered["layers"][0].get("roundCaps")) is True
    assert rendered["layers"][0].get("audioBus") == "bass"


def test_spectrum_glow_zero_stays_zero() -> None:
    """Glow 0 must not snap back to 0.45 via ``or`` defaults."""
    from features.studio.lib.scene_document import inspector_bind_state

    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionSpectrumShape": "bars",
            "compositionSpectrumMaterial": "neon",
            "compositionSpectrumGlow": 0.0,
        },
    )
    assert float(doc["composition"]["spectrum"]["glow"]) == 0.0
    state = inspector_bind_state(doc)
    assert float(state["compositionSpectrumGlow"]) == 0.0
    rendered = document_to_renderer_dict(doc)
    assert float(rendered["layers"][0].get("glow") or 0.0) == 0.0
    assert float(rendered["layers"][0].get("expertGlow") or 0.0) == 0.0


def test_performance_quality_changes_bar_count() -> None:
    base = {"compositionSpectrumShape": "circle", "compositionParticleType": "embers", "particlesEnabled": True}
    low = document_to_renderer_dict(
        apply_axis_patch(blank_studio_document(), {**base, "compositionPerformanceQuality": "low"})
    )
    high = document_to_renderer_dict(
        apply_axis_patch(blank_studio_document(), {**base, "compositionPerformanceQuality": "high"})
    )
    assert int(low["layers"][0]["barCount"]) < int(high["layers"][0]["barCount"])
    assert float(low["particlesSettings"]["spawnRate"]) < float(high["particlesSettings"]["spawnRate"])
    assert low["performanceSettings"]["quality"] == "low"
    assert high["performanceSettings"]["quality"] == "high"


def test_expert_controls_patch_all_axes() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "compositionPaletteIntensity": 1.4,
            "compositionBackgroundSaturation": 1.3,
            "compositionBackgroundHue": 20.0,
            "compositionSpectrumBlur": 2.0,
            "compositionSpectrumBarWidthScale": 1.5,
            "compositionLogoSize": 256.0,
            "compositionLogoOffsetX": 0.1,
            "compositionTextOpacity": 0.7,
            "compositionTextScale": 1.2,
            "compositionParticleSpeed": 1.8,
            "compositionLightingThickness": 1.4,
            "compositionLightingGlow": 0.9,
            "compositionCameraRollBias": 4.0,
            "compositionAudioBassEmphasis": 1.5,
            "compositionSpectrumShape": "circle",
            "compositionLightingEffect": "aura",
            "compositionTextEnabled": True,
            "albumEnabled": True,
            "albumManualText": "Expert",
        },
    )
    assert doc["composition"]["paletteIntensity"] == 1.4
    assert doc["composition"]["background"]["hue"] == 20.0
    assert doc["composition"]["spectrum"]["barWidthScale"] == 1.5
    assert doc["composition"]["logo"]["size"] == 256.0
    assert doc["composition"]["text"]["scale"] == 1.2
    assert doc["composition"]["particles"]["speed"] == 1.8
    assert doc["composition"]["lighting"]["thickness"] == 1.4
    assert doc["composition"]["camera"]["rollBias"] == 4.0
    assert doc["composition"]["audio"]["bassEmphasis"] == 1.5
    rendered = document_to_renderer_dict(doc, time_sec=0.5, audio_level=0.4)
    assert float(rendered["layers"][0]["blur"]) >= 2.0
    assert float(rendered["logoSettings"]["size"]) >= 256.0
    assert float(rendered["cameraSettings"]["roll"]) == 4.0
    assert float(rendered["audioSettings"]["bassEmphasis"]) == 1.5


def test_scroll_catalog_picker_selects_value(qapp: QApplication) -> None:
    from features.studio.widgets.scroll_catalog_picker import ScrollCatalogPicker

    picker = ScrollCatalogPicker()
    picker.set_options((("a", "Alpha"), ("b", "Beta")), include_none=False)
    seen: list[str] = []
    picker.selection_changed.connect(seen.append)
    picker.set_value("b", fallback="a")
    assert picker.current_data() == "b"
    # Programmatic set_value must not emit.
    assert seen == []
    picker._on_chip("a")
    assert picker.current_data() == "a"
    assert seen == ["a"]


def test_expert_float_slider_emits_value(qapp: QApplication) -> None:
    from features.studio.widgets.expert_slider import ExpertFloatSlider

    slider = ExpertFloatSlider("Input Gain", minimum=0.1, maximum=1.0, step=0.05, decimals=2, value=0.35)
    seen: list[float] = []
    slider.float_changed.connect(seen.append)
    assert abs(slider.current_float() - 0.35) < 1e-6
    assert "Input Gain (0.35)" in slider._caption.text()
    assert slider.height() == 22
    slider.set_float(0.4)
    assert seen == []
    assert "Input Gain (0.4)" in slider._caption.text()
    slider._slider.setValue(slider._to_slider(0.5))
    assert abs(slider.current_float() - 0.5) < 1e-6
    assert seen == [0.5]


def test_spectrum_inspector_section_cards(qapp: QApplication) -> None:
    from features.studio.widgets.inspectors import SpectrumInspector

    panel = SpectrumInspector()
    panel.set_expert_mode(True)
    assert panel._shape_card is not None
    assert panel._material_card is not None
    assert panel._animation_card is not None
    panel.bind(
        {
            "spectrumEnabled": True,
            "compositionSpectrumShape": "none",
            "compositionSpectrumMaterial": "none",
            "compositionSpectrumAnimation": "none",
            "compositionSpectrumSizeScale": 1.0,
            "compositionSpectrumLayers": [
                {"name": "Ring 1", "radiusOffset": 0.0, "opacity": 1.0, "enabled": True}
            ],
            "compositionSpectrumLayerIndex": 0,
            "compositionSpectrumBarHeight": 1.0,
            "compositionSpectrumGlow": 0.45,
            "compositionSpectrumOpacity": 1.0,
            "compositionSpectrumBlur": 0.0,
            "compositionSpectrumBarWidthScale": 1.0,
            "compositionSpectrumThicknessScale": 1.0,
        }
    )
    assert not panel._bar_height.isVisibleTo(panel)
    assert not panel._glow.isVisibleTo(panel)

    panel.bind(
        {
            "spectrumEnabled": True,
            "compositionSpectrumShape": "circle",
            "compositionSpectrumMaterial": "neon",
            "compositionSpectrumAnimation": "pulse",
            "compositionSpectrumSizeScale": 1.2,
            "compositionSpectrumLayers": [
                {"name": "Ring 1", "radiusOffset": 0.0, "opacity": 1.0, "enabled": True}
            ],
            "compositionSpectrumLayerIndex": 0,
            "compositionSpectrumBarHeight": 1.0,
            "compositionSpectrumGlow": 0.45,
            "compositionSpectrumOpacity": 1.0,
            "compositionSpectrumBlur": 0.0,
            "compositionSpectrumBarWidthScale": 1.0,
            "compositionSpectrumThicknessScale": 1.0,
        }
    )
    assert panel._bar_height.isVisibleTo(panel)
    assert panel._glow.isVisibleTo(panel)
    assert abs(panel._size.current_float() - 1.2) < 1e-6


def test_background_inspector_motion_tuning_visibility(qapp: QApplication) -> None:
    from features.studio.widgets.inspectors import BackgroundInspector

    panel = BackgroundInspector()
    panel.set_expert_mode(True)
    panel._sync_motion_tuning_ui("static")
    assert not panel._motion_speed.isVisibleTo(panel)
    assert not panel._motion_amp.isVisibleTo(panel)
    assert not panel._motion_zoom.isVisibleTo(panel)
    assert not panel._motion_warp.isVisibleTo(panel)

    panel._sync_motion_tuning_ui("slow_zoom")
    assert panel._motion_speed.isVisibleTo(panel)
    assert not panel._motion_amp.isVisibleTo(panel)
    assert panel._motion_zoom.isVisibleTo(panel)
    assert not panel._motion_warp.isVisibleTo(panel)

    panel._sync_motion_tuning_ui("warp")
    assert panel._motion_speed.isVisibleTo(panel)
    assert panel._motion_amp.isVisibleTo(panel)
    assert panel._motion_zoom.isVisibleTo(panel)
    assert panel._motion_warp.isVisibleTo(panel)

    panel._sync_motion_tuning_ui("ken_burns")
    assert "Pan strength" in panel._motion_amp._caption.text()


def test_inspector_host_scrolls_axis_panels(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QScrollArea

    from features.studio.widgets.inspector_host import InspectorHost

    host = InspectorHost()
    assert host._stack.count() >= 2
    # Tall axes (Spectrum) need scroll so combos/buttons keep natural height.
    for i in range(host._stack.count()):
        page = host._stack.widget(i)
        assert page is not None
        assert page.findChild(QScrollArea) is not None
        assert page.sizePolicy().verticalPolicy() == page.sizePolicy().Policy.Expanding


def test_audio_playlist_patch_keeps_active_track() -> None:
    doc = apply_axis_patch(
        blank_studio_document(),
        {
            "audioTracks": ["C:/music/a.mp3", "C:/music/b.mp3"],
            "audioPath": "C:/music/b.mp3",
        },
    )
    assert doc["assets"]["audio"] == "C:/music/b.mp3"
    assert doc["assets"]["audioTracks"] == ["C:/music/a.mp3", "C:/music/b.mp3"]
    removed = apply_axis_patch(doc, {"removeAudioTrack": "C:/music/b.mp3"})
    assert removed["assets"]["audio"] == "C:/music/a.mp3"
    assert removed["assets"]["audioTracks"] == ["C:/music/a.mp3"]


def test_studio_shell_matches_video_three_column_layout(qapp: QApplication) -> None:
    from features.studio.widgets.studio_shell import (
        STUDIO_LEFT_RAIL_WIDTH,
        STUDIO_RIGHT_RAIL_WIDTH,
        StudioShell,
    )

    shell = StudioShell()
    assert shell._left.minimumWidth() == STUDIO_LEFT_RAIL_WIDTH
    assert shell._right.minimumWidth() == STUDIO_RIGHT_RAIL_WIDTH
    assert shell._side_tabs.count() == 2
    assert shell._side_tabs.tabText(0) == "Inspector"
    assert shell._side_tabs.tabText(1) == "Developer"
    # Axis settings live on the right Inspector tab; AI sits under the scene tree.
    assert shell._inspector is shell._right._inspector
    assert shell._left._ai is not None
    # Export + tracks dock under the stage.
    assert shell._export_panel.objectName() == "account_card"
    assert shell._tracks.objectName() == "account_card"
    shell.bind_document(
        {
            "audioPath": "C:/music/song.mp3",
            "audioTracks": ["C:/music/song.mp3", "C:/music/other.wav"],
            "studioExport": {},
        }
    )
    assert "song.mp3" in shell._stage._track_label.text()
    assert shell._tracks._list.count() == 2
    shell.bind_document({"audioPath": "C:/music/only.mp3", "audioTracks": [], "studioExport": {}})
    assert shell._tracks._list.count() == 1


def test_studio_stage_preserves_position_when_duration_updates(qapp: QApplication) -> None:
    from features.studio.widgets.stage_panel import StudioStagePanel

    stage = StudioStagePanel()
    stage.set_position(70.0)
    stage.set_duration(0.0)
    assert stage._time_label.text().startswith("01:10")
    stage.set_duration(210.0)
    assert stage._time_label.text() == "01:10 / 03:30"
