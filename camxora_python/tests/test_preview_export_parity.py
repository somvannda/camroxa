"""Preview vs export JSON parity gate + lightning peak-override tests."""

from __future__ import annotations

from features.video.lib.lightning_render import (
    peak_lightning_flash_by_layer,
    sample_lightning_layer_peaks_over_interval,
)
from features.video.lib.lightning_style_registry import default_lightning_layer
from features.video.lib.preview_export_parity import (
    canonicalize_renderer_template,
    diff_renderer_templates,
    templates_match,
)
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def _base_template(**overrides) -> dict:
    tpl = normalize_renderer_template(default_renderer_template())
    tpl.update(overrides)
    return tpl


def test_canonicalize_matches_normalize() -> None:
    raw = default_renderer_template()
    assert canonicalize_renderer_template(raw) == normalize_renderer_template(raw)


def test_diff_equal_when_focus_keys_match() -> None:
    preview = _base_template(spectrumEnabled=True, lightningEnabled=True)
    export = canonicalize_renderer_template(dict(preview))
    report = diff_renderer_templates(preview, export)
    assert report.equal is True
    assert templates_match(preview, export) is True
    assert "match" in report.summary().lower()


def test_diff_reports_missing_spectrum_instance() -> None:
    preview = _base_template(
        spectrumEnabled=True,
        spectrumInstances=[
            {"id": "a", "enabled": True, "layers": [{"style": "ring", "bars": 64}]},
            {"id": "b", "enabled": True, "layers": [{"style": "bars", "bars": 32}]},
        ],
    )
    export = canonicalize_renderer_template(dict(preview))
    export["spectrumInstances"] = [dict(export["spectrumInstances"][0])]
    report = diff_renderer_templates(preview, export)
    assert report.equal is False
    joined = " ".join(report.changed + report.missing_in_export)
    assert "spectrumInstances" in joined


def test_diff_reports_changed_lightning_x() -> None:
    layer0 = default_lightning_layer()
    layer0["x"] = 10.0
    layer1 = default_lightning_layer()
    layer1["x"] = 40.0
    preview = _base_template(
        lightningEnabled=True,
        lightningLayers=[layer0, layer1],
    )
    export = canonicalize_renderer_template(dict(preview))
    export["lightningLayers"] = [dict(x) for x in export["lightningLayers"]]
    export["lightningLayers"][1]["x"] = 99.0
    report = diff_renderer_templates(preview, export)
    assert report.equal is False
    assert any("lightningLayers" in path and "x" in path for path in report.changed)


def test_diff_scrub_drift_on_logo_size() -> None:
    preview = _base_template()
    export = canonicalize_renderer_template(dict(preview))
    preview["logoSettings"] = dict(preview.get("logoSettings") or {})
    export["logoSettings"] = dict(export.get("logoSettings") or {})
    preview["logoSettings"]["size"] = 120.0
    export["logoSettings"]["size"] = 240.0
    report = diff_renderer_templates(preview, export)
    assert report.equal is False
    assert any("logoSettings" in path for path in report.changed)


def test_sample_peaks_only_include_struck_layers() -> None:
    """Per-layer peak map must not invent a floor for quiet sibling layers."""
    a = default_lightning_layer()
    a.update({"seed": 1.0, "flashRate": 2.0, "opacity": 1.0, "intensity": 1.0, "reactivity": 0.0})
    b = default_lightning_layer()
    # Extremely low flash rate + different seed → often quiet at the same sample.
    b.update({"seed": 99.0, "flashRate": 0.05, "opacity": 1.0, "intensity": 1.0, "reactivity": 0.0})
    tpl = _base_template(lightningEnabled=True, lightningLayers=[a, b])

    # Find a time where layer 0 flashes and layer 1 does not.
    found = None
    for i in range(400):
        t = i * (1.0 / 60.0)
        peaks = peak_lightning_flash_by_layer(tpl, time_sec=t, audio_env=0.0)
        if 0 in peaks and 1 not in peaks:
            found = t
            break
    assert found is not None, "expected a frame where only layer 0 flashes"

    # At the exact quiet-sibling instant, map is sparse (not every layer = peak).
    instant = peak_lightning_flash_by_layer(tpl, time_sec=found, audio_env=0.0)
    assert set(instant.keys()) == {0}

    global_peak, by_layer = sample_lightning_layer_peaks_over_interval(
        tpl,
        time_sec=found,
        encode_dt=1.0 / 60.0,  # one 60 Hz step — sibling stays quiet
        audio_env=0.0,
        sample_hz=60.0,
    )
    assert global_peak > 0.0
    assert set(by_layer.keys()) == {0}
    assert by_layer[0] == global_peak


def test_legacy_global_override_would_force_all_layers_but_per_layer_does_not() -> None:
    """Document the contract: per-layer floors are sparse; global override is dense."""
    layers = [default_lightning_layer(), default_lightning_layer(), default_lightning_layer()]
    for idx, layer in enumerate(layers):
        layer["seed"] = float(idx + 1)

    global_peak = 0.8
    legacy_floors = {i: global_peak for i in range(len(layers))}
    per_layer_floors = {0: global_peak}  # only the layer that peaked

    assert len(legacy_floors) == 3
    assert set(per_layer_floors.keys()) == {0}
    assert 1 not in per_layer_floors and 2 not in per_layer_floors
