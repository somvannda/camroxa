"""REQ-P2.2 apply_preview_patch without full normalize (no GL context required)."""

from __future__ import annotations

from visualizer_video.preview_widget import VideoSpectrumPreview


def test_apply_preview_patch_mutates_particles_without_normalize(monkeypatch) -> None:
    calls = {"normalize": 0}

    def _fake_normalize(tpl):
        calls["normalize"] += 1
        return tpl

    monkeypatch.setattr(
        "visualizer_video.preview_widget.normalize_renderer_template",
        _fake_normalize,
    )
    widget = VideoSpectrumPreview.__new__(VideoSpectrumPreview)
    widget.template = {"particlesSettings": {"opacity": 0.2, "size": 2.0}, "layers": [{"glow": 10}]}
    widget._spectrum_peak_cache = {"x": 1}
    widget._template_generation = 0
    widget._template_fingerprint = "old"
    widget._selected_spectrum_instance_index = 0
    widget.update = lambda: None  # type: ignore[method-assign]

    ok = VideoSpectrumPreview.apply_preview_patch(
        widget, {"particlesSettings": {"opacity": 0.55}}
    )
    assert ok is True
    assert widget.template["particlesSettings"]["opacity"] == 0.55
    assert widget._spectrum_peak_cache == {"x": 1}
    assert calls["normalize"] == 0


def test_apply_preview_patch_updates_layer_glow(monkeypatch) -> None:
    monkeypatch.setattr(
        "visualizer_video.preview_widget.normalize_renderer_template",
        lambda tpl: tpl,
    )
    widget = VideoSpectrumPreview.__new__(VideoSpectrumPreview)
    widget.template = {
        "layers": [{"glow": 10, "opacity": 1.0}],
        "spectrumInstances": [{"layers": [{"glow": 10, "opacity": 1.0}]}],
    }
    widget._spectrum_peak_cache = {"keep": True}
    widget._template_generation = 1
    widget._template_fingerprint = "x"
    widget._selected_spectrum_instance_index = 0
    widget.update = lambda: None  # type: ignore[method-assign]

    ok = VideoSpectrumPreview.apply_preview_patch(
        widget, {"layerIndex": 0, "layer": {"glow": 77}}
    )
    assert ok is True
    assert widget.template["layers"][0]["glow"] == 77.0
    assert widget.template["spectrumInstances"][0]["layers"][0]["glow"] == 77.0
    assert widget._spectrum_peak_cache == {"keep": True}


def test_apply_preview_patch_rejects_unknown_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        "visualizer_video.preview_widget.normalize_renderer_template",
        lambda tpl: tpl,
    )
    widget = VideoSpectrumPreview.__new__(VideoSpectrumPreview)
    widget.template = {"layers": [{"glow": 10}]}
    widget._spectrum_peak_cache = {}
    widget._template_generation = 0
    widget.update = lambda: None  # type: ignore[method-assign]
    assert (
        VideoSpectrumPreview.apply_preview_patch(
            widget, {"layerIndex": 0, "layer": {"glow": 1, "curved": True}}
        )
        is False
    )
