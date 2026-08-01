"""Tests for multi-Spectrum instances."""

from __future__ import annotations

from features.video.lib.spectrum_instance_registry import (
    apply_draft_fields_to_instance,
    default_spectrum_instance,
    iter_render_spectrum_instances,
    migrate_legacy_spectrum_to_instances,
    normalize_spectrum_instances,
    project_instance_to_draft_fields,
)
from features.video.lib.video_template_draft import build_video_template_draft
from features.video.lib.video_template_save import build_video_workspace_template_save_patch
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def test_legacy_template_migrates_to_one_instance() -> None:
    tpl = normalize_renderer_template(default_renderer_template())
    instances = migrate_legacy_spectrum_to_instances(tpl)
    assert len(instances) == 1
    assert instances[0]["style"]
    assert isinstance(instances[0]["layers"], list)


def test_legacy_sensitivity_maps_to_input_gain() -> None:
    tpl = {
        "style": "orbit-spikes",
        "layers": [{"thickness": 40, "barWidth": 4}],
        "audioSettings": {"sensitivity": 3.5, "smoothing": 0.35},
    }
    instances = migrate_legacy_spectrum_to_instances(tpl)
    audio = instances[0]["audioSettings"]
    assert audio["inputGain"] == 3.5
    assert audio["sensitivity"] == 3.5
    assert abs(audio["motionSmoothing"] - 0.35) < 1e-6


def test_empty_instance_layers_heal_from_template() -> None:
    layers = [{"id": "ring", "thickness": 55, "barWidth": 3}]
    tpl = {
        "layers": layers,
        "spectrumInstances": [
            {
                "id": "spectrum-1",
                "enabled": True,
                "style": "orbit-spikes",
                "layers": [],
                "audioSettings": {"inputGain": 2.0},
            }
        ],
    }
    jobs = iter_render_spectrum_instances(tpl)
    assert len(jobs) == 1
    assert len(jobs[0]["layers"]) == 1
    assert jobs[0]["layers"][0]["thickness"] == 55
    assert jobs[0]["audioSettings"]["inputGain"] == 2.0


def test_save_does_not_wipe_layers_when_instance_empty() -> None:
    layers = [{"id": "ring", "thickness": 70, "barWidth": 5, "curved": True, "mirrored": True}]
    tpl = normalize_renderer_template(
        {
            **default_renderer_template(),
            "layers": layers,
            "audioSettings": {"sensitivity": 2.2},
        }
    )
    draft = build_video_template_draft(tpl, logo_path="")
    empty_inst = {
        **default_spectrum_instance(index=1),
        "layers": [],
        "audioSettings": {"inputGain": 1.0},
    }
    patch = build_video_workspace_template_save_patch(
        template=tpl,
        draft=draft,
        template_name="t",
        layers=layers,
        spectrum_instances=[empty_inst],
    )
    assert len(patch.get("layers") or []) == 1
    assert patch["layers"][0]["thickness"] == 70
    assert len((patch.get("spectrumInstances") or [{}])[0].get("layers") or []) == 1


def test_normalize_keeps_multiple_instances() -> None:
    raw = [
        default_spectrum_instance(index=1, layers=[{"curved": True, "thickness": 40}]),
        default_spectrum_instance(index=2, layers=[{"curved": False, "thickness": 20}]),
    ]
    raw[1]["x"] = 80.0
    raw[1]["spectrumAttachToLogo"] = False
    out = normalize_spectrum_instances(raw)
    assert len(out) == 2
    assert out[1]["x"] == 80.0
    assert out[1]["spectrumAttachToLogo"] is False


def test_iter_render_skips_disabled() -> None:
    tpl = {
        "spectrumInstances": [
            {**default_spectrum_instance(index=1), "enabled": True, "layers": [{"thickness": 10}]},
            {**default_spectrum_instance(index=2), "enabled": False, "layers": [{"thickness": 10}]},
        ]
    }
    jobs = iter_render_spectrum_instances(tpl)
    assert len(jobs) == 1


def test_project_and_apply_draft_roundtrip() -> None:
    inst = default_spectrum_instance(index=1)
    inst["x"] = 12.0
    inst["audioSettings"]["inputGain"] = 2.5
    draft = project_instance_to_draft_fields(inst)
    assert draft["positionX"] == 12.0
    assert draft["audioInputGain"] == 2.5
    updated = apply_draft_fields_to_instance(inst, {"positionX": 40.0, "audioInputGain": 1.2})
    assert updated["x"] == 40.0
    assert updated["audioSettings"]["inputGain"] == 1.2


def test_normalize_renderer_includes_spectrum_instances() -> None:
    out = normalize_renderer_template(default_renderer_template())
    assert isinstance(out.get("spectrumInstances"), list)
    assert len(out["spectrumInstances"]) >= 1


def test_magma_ridge_style_syncs_onto_instance() -> None:
    """Preset apply must push style into the instance or preview keeps drawing bars."""
    from features.video.lib.spectrum_style_registry import build_spectrum_preset_template
    from visualizer.gpu_render import _resolve_export_spectrum_style

    base = {
        "style": "orbit-spikes",
        "layers": [{"curved": True, "mirrored": True, "fillCircle": False, "thickness": 30, "barWidth": 4}],
    }
    patched = build_spectrum_preset_template(base, "magma-ridge", replace_stack=True)
    assert patched["style"] == "magma-ridge"

    inst = default_spectrum_instance(index=1, layers=base["layers"])
    assert inst["style"] == "orbit-spikes"
    # Without sync, layer fillCircle alone still resolves as orbit-spikes bars.
    assert _resolve_export_spectrum_style(inst["style"], patched["layers"][0]) == "orbit-spikes"

    draft = project_instance_to_draft_fields(inst)
    draft["style"] = patched["style"]
    synced = apply_draft_fields_to_instance(inst, draft)
    synced["layers"] = list(patched["layers"])
    assert synced["style"] == "magma-ridge"
    assert _resolve_export_spectrum_style(synced["style"], synced["layers"][0]) == "magma-ridge"
