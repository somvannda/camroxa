"""Auto-Video / saved-template renderer must match Manual Export domains."""

from __future__ import annotations

from features.video.lib.lightning_style_registry import default_lightning_layer
from features.video.lib.preview_export_parity import diff_renderer_templates
from features.video.lib.video_template_draft import build_video_template_draft, clone_layer_records
from features.video.lib.video_template_save import build_video_workspace_template_save_patch
from features.video.services.template_normalizer import TemplateNormalizer
from shared.lib.export_tiers import resolve_export_tier_settings


def _rich_saved_template() -> dict:
    bolts = []
    for i, color in enumerate(("#ff0000", "#00ff88", "#4488ff"), start=1):
        bolt = default_lightning_layer(index=i)
        bolt["x"] = float(i * 40)
        bolt["color"] = {
            "mode": "solid",
            "solidColor": color,
            "gradientColors": [color, "#ffffff"],
        }
        bolt["blend"] = "add"
        bolts.append(bolt)
    ring = {
        "id": "ring-1",
        "name": "Ring",
        "opacity": 0.9,
        "glow": 0.75,
        "glowStrength": 0.8,
        "blend": "add",
        "thickness": 48.0,
        "barWidth": 4.0,
        "color": {
            "mode": "gradient",
            "solidColor": "#a855f7",
            "gradientColors": ["#ffffff", "#a855f7", "#38bdf8"],
        },
    }
    return {
        "templateName": "parity-rich",
        "style": "orbit-spikes",
        "spectrumEnabled": True,
        "lightningEnabled": True,
        "lightningLayers": bolts,
        "layers": [dict(ring)],
        "spectrumInstances": [
            {
                "id": "spectrum-1",
                "enabled": True,
                "style": "orbit-spikes",
                "layers": [dict(ring)],
                "audioSettings": {"inputGain": 2.4, "motionSmoothing": 0.4},
            }
        ],
        "particlesSettings": {"enabled": True, "maxCount": 40, "glow": 0.5},
        "logoSettings": {"enabled": True, "size": 120},
        "effects": {
            "vignette": {"enabled": True, "strength": 0.4, "opacity": 0.5, "reactivity": 0.2},
            "smoke": {"enabled": False},
        },
        "previewBackground": "C:/preview-only.png",
        "audioSettings": {"inputGain": 2.0, "smoothing": 0.35},
    }


def test_save_patch_none_lightning_keeps_saved_bolts() -> None:
    base = _rich_saved_template()
    draft = build_video_template_draft(base, logo_path="", background_path="")
    draft["lightningEnabled"] = True
    patch = build_video_workspace_template_save_patch(
        template=base,
        draft=draft,
        template_name="parity-rich",
        layers=base["layers"],
        lightning_layers=None,
    )
    assert len(patch["lightningLayers"]) == 3
    assert [layer["color"]["solidColor"] for layer in patch["lightningLayers"]] == [
        "#ff0000",
        "#00ff88",
        "#4488ff",
    ]


def test_from_saved_workspace_matches_manual_shaped_builder() -> None:
    base = _rich_saved_template()
    normalizer = TemplateNormalizer()
    draft = build_video_template_draft(base, logo_path="logo.png", background_path="")
    draft["lightningEnabled"] = True
    track_paths = [r"D:\tracks\a.mp3", r"D:\tracks\b.mp3"]

    manual_shaped = normalizer.to_renderer_dict(
        base=base,
        draft=draft,
        layers=clone_layer_records(base["layers"]),
        lightning_layers=clone_layer_records(base["lightningLayers"]),
        spectrum_instances=clone_layer_records(base["spectrumInstances"]),
        workspace={
            "logoPath": "logo.png",
            "trackPaths": track_paths,
            "pipelineAlbum": "Demo Album",
        },
        track_paths=track_paths,
        active_track_path=None,
    )
    auto = normalizer.from_saved_workspace(
        base,
        logo_path="logo.png",
        track_paths=track_paths,
        pipeline_album="Demo Album",
        clear_preview_background=True,
    )

    report = diff_renderer_templates(manual_shaped, auto)
    assert report.equal, report.summary(limit=20)
    assert len(auto["lightningLayers"]) == 3
    assert auto["lightningEnabled"] is True

    instances = auto.get("spectrumInstances") or []
    assert instances
    primary_layers = instances[0].get("layers") if isinstance(instances[0], dict) else []
    assert primary_layers
    layer0 = primary_layers[0]
    assert str(layer0.get("blend") or "").lower() in {"add", "screen", "lighten", "normal"}
    color = layer0.get("color") if isinstance(layer0.get("color"), dict) else {}
    grads = color.get("gradientColors") if isinstance(color.get("gradientColors"), list) else []
    assert len(grads) >= 2
    # Preview-only background must not leak into pipeline renderer.
    assert not str(auto.get("previewBackground") or "").strip()


def test_auto_export_tier_defaults_match_manual_not_draft() -> None:
    auto_default = resolve_export_tier_settings({}, pipeline=True)
    manual_default = resolve_export_tier_settings({}, pipeline=False)
    # Automation now uses Manual semantics (pipeline=False) so Standard wins.
    aligned = resolve_export_tier_settings({}, pipeline=False)
    assert aligned.tier == manual_default.tier == "standard"
    assert aligned.resolution == manual_default.resolution
    assert auto_default.tier == "draft"  # legacy helper still Draft when asked


def test_auto_speed_keeps_spectrum_glow_melt_like_preview() -> None:
    """Preview + Manual keep dual glow; Auto must not silently use very_fast."""
    from visualizer.gpu_render import export_glow_pass_limit
    from shared.lib.export_codec import normalize_export_speed_mode
    from shared.lib.export_tiers import resolve_export_tier_settings

    tier = resolve_export_tier_settings({}, pipeline=False)
    speed_mode = normalize_export_speed_mode(None, default=tier.speed_mode)
    if tier.tier != "draft" and speed_mode in {"very_fast", "draft"}:
        speed_mode = "balanced"
    assert export_glow_pass_limit(speed_mode) == 2
