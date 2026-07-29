"""Lightning layers + geometry smoke tests."""

from __future__ import annotations

import numpy as np

from features.video.lib.lightning_geometry import build_lightning_polylines, lightning_flash_envelope
from features.video.lib.lightning_style_registry import (
    LIGHTNING_STYLE_OPTIONS,
    default_lightning_layer,
    normalize_lightning_layers,
    normalize_lightning_style,
)
from visualizer.template_runtime import default_renderer_template, normalize_renderer_template


def test_ten_lightning_styles_registered() -> None:
    assert len(LIGHTNING_STYLE_OPTIONS) == 10
    keys = [key for key, _ in LIGHTNING_STYLE_OPTIONS]
    assert "fork" in keys and "horizon" in keys


def test_normalize_layers_defaults() -> None:
    layers = normalize_lightning_layers(None)
    assert len(layers) == 1
    assert layers[0]["style"] == "fork"
    assert normalize_lightning_style("NOPE") == "fork"


def test_template_includes_lightning_layers() -> None:
    out = normalize_renderer_template(default_renderer_template())
    assert out["lightningEnabled"] is True
    assert isinstance(out["lightningLayers"], list)
    assert len(out["lightningLayers"]) >= 1


def test_geometry_builds_for_each_style() -> None:
    flash = lightning_flash_envelope(
        time_sec=1.25,
        flash_rate=1.0,
        speed=1.0,
        reactivity=0.2,
        audio_env=0.8,
        seed=2.0,
    )
    assert 0.0 <= flash <= 1.0
    for style, _label in LIGHTNING_STYLE_OPTIONS:
        polys = build_lightning_polylines(
            style=style,
            cx=100.0,
            cy=100.0,
            length_px=160.0,
            direction="down",
            branchiness=0.6,
            time_sec=1.25,
            flash=max(0.2, flash),
            seed=3.0,
        )
        assert isinstance(polys, list)
        assert len(polys) >= 1
        assert polys[0].shape[1] == 2


def test_default_layer_shape() -> None:
    layer = default_lightning_layer(index=2)
    assert layer["id"] == "lightning-2"
    assert layer["name"] == "Bolt 2"
