"""P0 composition scene contract — architecture tree JSON."""

from __future__ import annotations

import json
from pathlib import Path

from features.video.lib.composition_scene_contract import (
    OVERLAY_LEGACY_KEYS,
    SCENE_OBJECTS,
    TEXT_LEGACY_KEYS,
    composition_from_legacy_template,
    composition_legacy_key_map,
    default_composition_scene,
    ensure_composition_on_template,
    legacy_background_motion_mode,
    normalize_composition_scene,
    strip_composition_for_renderer,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "video"


def test_layer1_scene_objects_locked() -> None:
    assert SCENE_OBJECTS == (
        "background",
        "spectrum",
        "logo",
        "text",
        "particles",
        "lighting",
        "camera",
        "audio",
        "overlay",
    )
    assert "text" in SCENE_OBJECTS and "overlay" in SCENE_OBJECTS
    assert TEXT_LEGACY_KEYS == ("albumText", "titleText", "textOverlays")
    assert OVERLAY_LEGACY_KEYS == ("overlaySettings",)


def test_default_composition_matches_golden_fixture() -> None:
    expected = json.loads((FIXTURES / "composition_default_scene.json").read_text(encoding="utf-8"))
    assert default_composition_scene() == expected
    assert normalize_composition_scene(None) == expected
    assert normalize_composition_scene({}) == expected


def test_composition_from_legacy_projects_motion_and_domains() -> None:
    template = {
        "style": "Orbit-Spikes",
        "backgroundSettings": {"motionMode": "zoom"},
        "logoSettings": {"enabled": True, "spinEnabled": True},
        "albumText": {"enabled": True},
        "particlesSettings": {"enabled": True, "variant": "Dust"},
        "lightningLayers": [{"style": "Fork", "trigger": "Bass"}],
        "effects": {
            "smoke": {"enabled": True},
            "vignette": {"enabled": True},
            "camera_shake": {"enabled": True},
        },
        "overlaySettings": {"enabled": True, "items": [{"id": "frame-1"}]},
    }
    scene = composition_from_legacy_template(template)
    assert scene["background"]["motion"] == "slow_zoom"
    assert scene["background"]["atmosphere"] == "smoke"
    assert scene["spectrum"]["shape"] == "orbit-spikes"
    assert scene["logo"]["animation"] == "rotate"
    assert scene["text"]["enabled"] is True
    assert scene["overlay"]["enabled"] is True
    assert scene["overlay"]["items"] == [{"id": "frame-1"}]
    assert scene["particles"]["type"] == "dust"
    assert scene["lighting"]["effect"] == "fork"
    assert scene["lighting"]["trigger"] == "bass"
    assert scene["camera"]["behavior"] == "shake"
    assert "vignette" in scene["postProcessing"]["effects"]
    assert scene["audio"]["mapping"] == {}


def test_ensure_and_strip_composition() -> None:
    template = {
        "composition": {
            "version": 1,
            "spectrum": {"shape": "circle", "material": "neon", "animation": "pulse"},
        }
    }
    ensure_composition_on_template(template)
    assert isinstance(template.get("composition"), dict)

    kept = strip_composition_for_renderer(template)
    assert "composition" in kept
    assert kept["composition"]["spectrum"]["shape"] in (
        "circle",
        template["composition"]["spectrum"]["shape"],
    )


def test_legacy_motion_roundtrip_helpers() -> None:
    assert legacy_background_motion_mode("static") == "none"
    assert legacy_background_motion_mode("slow_zoom") == "zoom"
    assert legacy_background_motion_mode("vibrate") == "vibrate"


def test_template_normalizer_keeps_composition_engine_v1() -> None:
    from features.video.lib.video_template_draft import build_video_template_draft
    from features.video.services.template_normalizer import TemplateNormalizer

    base = {
        "schema": "camxora.composition",
        "spectrumEnabled": True,
        "layers": [],
        "textOverlays": [],
        "composition": {
            "version": 1,
            "spectrum": {"shape": "circle", "material": "neon", "animation": "pulse"},
            "particles": {"type": "none", "behavior": "none"},
            "logo": {"enabled": True, "animation": "none"},
            "background": {"image": None, "motion": "static", "atmosphere": "none"},
            "text": {"enabled": False},
            "overlay": {"enabled": False, "animation": "none", "items": []},
            "lighting": {"effect": "none", "trigger": "none"},
            "camera": {"behavior": "none"},
            "postProcessing": {"effects": []},
            "audio": {"mapping": {}},
            "colorPalette": "cyberpunk",
        },
        "assets": {"backgroundImage": None, "logo": None, "audio": None},
    }
    draft = build_video_template_draft(base, logo_path="")
    out = TemplateNormalizer().to_renderer_dict(
        base=base,
        draft=draft,
        layers=[],
        workspace={},
    )
    assert "composition" in out
    assert out["composition"]["spectrum"]["shape"] == "circle"
    assert out["engine"]["compiled"] is True
    assert "style" not in out


def test_legacy_key_map_covers_architecture_tree() -> None:
    mapping = composition_legacy_key_map()
    for key in (
        "composition.background.motion",
        "composition.spectrum.shape",
        "composition.spectrum.material",
        "composition.text.enabled",
        "composition.overlay.enabled",
        "composition.audio.mapping",
        "composition.colorPalette",
    ):
        assert key in mapping
