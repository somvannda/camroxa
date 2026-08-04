"""Export WYSIWYG: spectrum draw jobs + live draft template shipping."""

from __future__ import annotations

from features.video.lib.spectrum_instance_registry import default_spectrum_instance
from features.video.services.template_normalizer import TemplateNormalizer
from visualizer.gpu_render import _gpu_spectrum_layer_key, _spectrum_draw_jobs
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def test_gpu_spectrum_layer_key_unique_per_instance() -> None:
    assert _gpu_spectrum_layer_key(0, 3) == 3
    assert _gpu_spectrum_layer_key(1, 3) == 259
    assert _gpu_spectrum_layer_key(0, 3) != _gpu_spectrum_layer_key(1, 3)


def test_spectrum_draw_jobs_uses_multi_instances() -> None:
    layers_a = [{"id": "a", "thickness": 10, "barWidth": 4}]
    layers_b = [{"id": "b", "thickness": 20, "barWidth": 8}]
    tpl = {
        "spectrumEnabled": True,
        "style": "orbit-spikes",
        "layers": layers_a,
        "position": {"x": 0, "y": 0, "anchor": "center"},
        "spectrumInstances": [
            {
                **default_spectrum_instance(index=1, layers=layers_a),
                "style": "magma-ridge",
                "x": 40.0,
                "y": -12.0,
                "enabled": True,
            },
            {
                **default_spectrum_instance(index=2, layers=layers_b),
                "style": "orbit-spikes",
                "x": -80.0,
                "y": 55.0,
                "enabled": True,
                "spectrumAttachToLogo": False,
            },
        ],
    }
    jobs = _spectrum_draw_jobs(tpl)
    assert len(jobs) == 2
    assert jobs[0]["style"] == "magma-ridge"
    assert jobs[0]["x"] == 40.0
    assert jobs[1]["x"] == -80.0
    assert jobs[1]["layers"][0]["id"] == "b"


def test_to_renderer_dict_ships_live_draft_and_instances() -> None:
    from features.video.lib.video_template_draft import build_video_template_draft

    base = normalize_renderer_template(default_renderer_template())
    full_draft = build_video_template_draft(base, logo_path="")
    full_draft["logoPositionX"] = 33.0
    full_draft["logoPositionY"] = -21.0
    full_draft["positionX"] = 33.0
    full_draft["positionY"] = -21.0
    full_draft["style"] = "magma-ridge"
    full_draft["backgroundBrightness"] = 1.4

    live_layers = [{"id": "live", "thickness": 77, "barWidth": 12, "curved": True}]
    live_inst = {
        **default_spectrum_instance(index=1, layers=live_layers),
        "style": "magma-ridge",
        "x": 33.0,
        "y": -21.0,
    }
    out = TemplateNormalizer().to_renderer_dict(
        base=base,
        draft=full_draft,
        layers=live_layers,
        workspace={"logoPath": "", "trackPaths": []},
        spectrum_instances=[live_inst],
    )
    assert out["logoSettings"]["position"]["x"] == 33.0
    assert out["logoSettings"]["position"]["y"] == -21.0
    assert out["backgroundSettings"]["brightness"] == 1.4
    assert (out.get("spectrumInstances") or [{}])[0]["style"] == "magma-ridge"
    assert (out.get("spectrumInstances") or [{}])[0]["layers"][0]["id"] == "live"
    jobs = _spectrum_draw_jobs(out)
    assert len(jobs) >= 1
    assert jobs[0]["x"] == 33.0
    assert jobs[0]["style"] == "magma-ridge"
