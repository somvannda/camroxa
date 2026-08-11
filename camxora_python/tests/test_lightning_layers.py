"""Lightning layers + geometry smoke tests."""

from __future__ import annotations

import numpy as np

from features.video.lib.lightning_geometry import (
    build_lightning_polylines,
    lightning_flash_envelope,
    polyline_to_ndc_strip,
)
from features.video.lib.lightning_style_registry import (
    LIGHTNING_PRESET_OPTIONS,
    LIGHTNING_STYLE_OPTIONS,
    LIGHTNING_TRIGGER_OPTIONS,
    MAX_LIGHTNING_LAYERS,
    build_lightning_preset_layer_patch,
    default_lightning_layer,
    is_lightning_preset_key,
    normalize_lightning_layers,
    normalize_lightning_style,
    normalize_lightning_trigger,
)
from features.video.lib.video_template_draft import build_video_template_draft
from features.video.services.template_normalizer import TemplateNormalizer
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


def test_max_lightning_layers_is_ten() -> None:
    assert MAX_LIGHTNING_LAYERS == 10


def test_normalize_lightning_layers_caps_at_max() -> None:
    raw = [default_lightning_layer(index=i) for i in range(1, MAX_LIGHTNING_LAYERS + 4)]
    layers = normalize_lightning_layers(raw)
    assert len(layers) == MAX_LIGHTNING_LAYERS
    assert layers[-1]["id"] == f"lightning-{MAX_LIGHTNING_LAYERS}"


def test_export_normalizer_keeps_ten_lightning_layers() -> None:
    bolts = [default_lightning_layer(index=i) for i in range(1, MAX_LIGHTNING_LAYERS + 1)]
    for i, bolt in enumerate(bolts):
        bolt["x"] = float(i * 25)
        bolt["enabled"] = True
    base = {
        "templateName": "ten-bolts",
        "style": "orbit-spikes",
        "lightningEnabled": True,
        "lightningLayers": [default_lightning_layer(index=1)],
        "spectrumEnabled": True,
        "layers": [{"opacity": 1.0, "glow": 0.5}],
    }
    draft = build_video_template_draft(base, logo_path="", background_path="")
    draft["lightningEnabled"] = True
    out = TemplateNormalizer().to_renderer_dict(
        base=base,
        draft=draft,
        layers=base["layers"],
        workspace={},
        lightning_layers=bolts,
    )
    assert out["lightningEnabled"] is True
    assert len(out["lightningLayers"]) == MAX_LIGHTNING_LAYERS
    assert [layer["x"] for layer in out["lightningLayers"]] == [float(i * 25) for i in range(MAX_LIGHTNING_LAYERS)]


def test_template_includes_lightning_layers() -> None:
    out = normalize_renderer_template(default_renderer_template())
    assert out["lightningEnabled"] is False
    assert isinstance(out["lightningLayers"], list)
    assert len(out["lightningLayers"]) >= 1


def test_polyline_strip_ndc() -> None:
    pts = np.array([[100.0, 100.0], [140.0, 180.0], [120.0, 240.0]], dtype=np.float32)
    strip = polyline_to_ndc_strip(pts, half_width=2.0, frame_w=800.0, frame_h=450.0)
    assert strip is not None
    assert strip.shape == (6, 2)


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
            speed=1.0,
        )
        assert isinstance(polys, list)
        assert len(polys) >= 1
        assert polys[0].shape[1] == 2


def test_one_bolt_per_layer_storm_and_spider() -> None:
    """Storm/spider must not spawn independent multi-bolt fans."""
    storm = build_lightning_polylines(
        style="storm",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=1.0,
        time_sec=1.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
    )
    spider = build_lightning_polylines(
        style="spider",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=1.0,
        time_sec=1.0,
        flash=1.0,
        seed=2.0,
        speed=1.0,
    )
    # Main path + at most 2 side forks → at most 3 polylines.
    assert 1 <= len(storm) <= 3
    assert 1 <= len(spider) <= 3


def test_speed_grows_bolt_length() -> None:
    """Length is stable by default; Length React optionally stretches with flash."""
    quiet = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=0.2,
        seed=1.0,
        speed=1.0,
        length_reactivity=0.0,
    )[0]
    loud = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
        length_reactivity=0.0,
    )[0]
    quiet_span = float(np.linalg.norm(quiet[-1] - quiet[0]))
    loud_span = float(np.linalg.norm(loud[-1] - loud[0]))
    assert abs(loud_span - quiet_span) < 1.0

    soft = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=0.2,
        seed=1.0,
        speed=1.0,
        length_reactivity=1.0,
    )[0]
    hard = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
        length_reactivity=1.0,
    )[0]
    soft_span = float(np.linalg.norm(soft[-1] - soft[0]))
    hard_span = float(np.linalg.norm(hard[-1] - hard[0]))
    assert hard_span > soft_span * 1.15


def test_zero_floats_are_preserved() -> None:
    layers = normalize_lightning_layers(
        [
            {
                "opacity": 0.0,
                "glow": 0.0,
                "branchiness": 0.0,
                "intensity": 0.0,
                "reactivity": 0.0,
                "thickness": 0.0,
                "speed": 0.0,
                "flashRate": 0.0,
                "lengthReactivity": 0.0,
                "taper": 0.0,
                "reactMotionSpeed": 0.0,
            }
        ]
    )
    layer = layers[0]
    assert layer["opacity"] == 0.0
    assert layer["glow"] == 0.0
    assert layer["branchiness"] == 0.0
    assert layer["intensity"] == 0.0
    assert layer["reactivity"] == 0.0
    assert layer["thickness"] == 0.0
    assert layer["speed"] == 0.0
    assert layer["flashRate"] == 0.0
    assert layer["spawnMode"] == "fixed"
    assert layer["taper"] == 0.0


def test_polyline_taper_width() -> None:
    pts = np.array([[100.0, 100.0], [140.0, 180.0], [120.0, 240.0]], dtype=np.float32)
    strip = polyline_to_ndc_strip(
        pts, half_width=1.0, half_width_end=4.0, frame_w=800.0, frame_h=450.0
    )
    assert strip is not None
    assert strip.shape == (6, 2)


def test_branchiness_zero_means_no_forks() -> None:
    storm = build_lightning_polylines(
        style="storm",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=1.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
    )
    assert len(storm) == 1


def test_wandering_preset_is_random_spawn() -> None:
    assert is_lightning_preset_key("wandering_bolt")
    patch = build_lightning_preset_layer_patch("wandering_bolt")
    assert patch is not None
    assert patch["spawnMode"] == "random"
    merged = normalize_lightning_layers([{**default_lightning_layer(index=1), **patch}])[0]
    assert merged["spawnMode"] == "random"


def test_default_layer_shape() -> None:
    layer = default_lightning_layer(index=2)
    assert layer["id"] == "lightning-2"
    assert layer["name"] == "Bolt 2"
    assert layer["trigger"] == "always"
    assert layer["seedLock"] is False
    assert layer["rotation"] == 0.0
    assert "glow" in layer and "branchiness" in layer


def test_rotation_spins_bolt_direction() -> None:
    base = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
        rotation=0.0,
    )[0]
    spun = build_lightning_polylines(
        style="ribbon",
        cx=0.0,
        cy=0.0,
        length_px=200.0,
        direction="down",
        branchiness=0.0,
        time_sec=0.0,
        flash=1.0,
        seed=1.0,
        speed=1.0,
        rotation=90.0,
    )[0]
    base_dir = base[-1] - base[0]
    spun_dir = spun[-1] - spun[0]
    # 90° clockwise from down (0, +y) → roughly left (-x)
    assert abs(float(base_dir[0])) < abs(float(base_dir[1]))
    assert abs(float(spun_dir[1])) < abs(float(spun_dir[0]))
    assert float(spun_dir[0]) < 0.0


def test_normalize_preserves_trigger_and_seed_lock() -> None:
    layers = normalize_lightning_layers(
        [
            {
                "style": "neon",
                "trigger": "kick",
                "triggerThreshold": 0.4,
                "seed": 42,
                "seedLock": True,
                "glow": 0.9,
                "branchiness": 0.2,
            }
        ]
    )
    assert layers[0]["trigger"] == "kick"
    assert layers[0]["triggerThreshold"] == 0.4
    assert layers[0]["seed"] == 42.0
    assert layers[0]["seedLock"] is True
    assert normalize_lightning_trigger("NOPE") == "always"
    assert len(LIGHTNING_TRIGGER_OPTIONS) == 6


def test_flash_envelope_trigger_modes() -> None:
    # Find a time inside the strike duty window for seed=1.
    timed_on = 0.0
    for t in [i * 0.02 for i in range(80)]:
        v = lightning_flash_envelope(
            time_sec=t,
            flash_rate=1.0,
            speed=1.0,
            reactivity=0.0,
            audio_env=0.0,
            seed=1.0,
            trigger="timed",
        )
        if v > 0.2:
            timed_on = v
            break
    assert timed_on > 0.2

    # Between strikes, continuous audio must NOT keep lightning permanently on.
    mid_strike_off = None
    for t in [i * 0.02 for i in range(80)]:
        v = lightning_flash_envelope(
            time_sec=t,
            flash_rate=1.0,
            speed=1.0,
            reactivity=1.0,
            audio_env=1.0,
            seed=1.0,
            trigger="always",
        )
        if v <= 0.02:
            mid_strike_off = v
            break
    assert mid_strike_off is not None

    kick_hit = lightning_flash_envelope(
        time_sec=0.0,
        flash_rate=1.0,
        speed=1.0,
        reactivity=1.0,
        audio_env=0.0,
        seed=1.0,
        trigger="kick",
        kick=0.9,
        threshold=0.22,
    )
    kick_miss = lightning_flash_envelope(
        time_sec=0.0,
        flash_rate=1.0,
        speed=1.0,
        reactivity=1.0,
        audio_env=0.0,
        seed=1.0,
        trigger="kick",
        kick=0.05,
        threshold=0.22,
    )
    beat_hit = lightning_flash_envelope(
        time_sec=0.0,
        flash_rate=1.0,
        speed=1.0,
        reactivity=1.0,
        audio_env=0.0,
        seed=1.0,
        trigger="beat",
        beat=0.0,
        onset=0.8,
        threshold=0.22,
    )
    assert kick_hit > kick_miss
    assert beat_hit > 0.4

    bass_hit = lightning_flash_envelope(
        time_sec=0.0,
        flash_rate=1.0,
        speed=1.0,
        reactivity=1.0,
        audio_env=0.0,
        seed=1.0,
        trigger="bass",
        bass=0.9,
        threshold=0.22,
    )
    bass_miss = lightning_flash_envelope(
        time_sec=0.0,
        flash_rate=1.0,
        speed=1.0,
        reactivity=1.0,
        audio_env=0.0,
        seed=1.0,
        trigger="bass",
        bass=0.05,
        threshold=0.22,
    )
    assert bass_hit > bass_miss


def test_presets_apply_patches() -> None:
    assert len(LIGHTNING_PRESET_OPTIONS) >= 6
    assert is_lightning_preset_key("neon_sky")
    assert not is_lightning_preset_key("missing")
    for key, _label in LIGHTNING_PRESET_OPTIONS:
        patch = build_lightning_preset_layer_patch(key)
        assert isinstance(patch, dict)
        assert "style" in patch
        assert "trigger" in patch
        merged = normalize_lightning_layers([{**default_lightning_layer(index=1), **patch}])[0]
        assert merged["style"] == patch["style"]


def test_vignette_reactivity_opens_on_flash() -> None:
    from features.video.lib.lightning_render import apply_vignette_reactivity, peak_lightning_flash

    strength, opacity = apply_vignette_reactivity(
        strength=0.6,
        opacity=0.8,
        reactivity=2.0,
        flash_env=1.0,
    )
    assert strength < 0.6
    assert opacity < 0.8

    quiet = peak_lightning_flash(
        {"lightningEnabled": False, "lightningLayers": []},
        time_sec=1.0,
        kick=1.0,
    )
    assert quiet == 0.0

    hit = peak_lightning_flash(
        {
            "lightningEnabled": True,
            "lightningLayers": [
                {
                    "enabled": True,
                    "trigger": "kick",
                    "triggerThreshold": 0.2,
                    "intensity": 1.0,
                    "reactivity": 1.0,
                    "flashRate": 1.0,
                    "speed": 1.0,
                    "seed": 1.0,
                }
            ],
        },
        time_sec=0.0,
        kick=0.95,
        audio_env=0.0,
    )
    miss = peak_lightning_flash(
        {
            "lightningEnabled": True,
            "lightningLayers": [
                {
                    "enabled": True,
                    "trigger": "kick",
                    "triggerThreshold": 0.2,
                    "intensity": 1.0,
                    "reactivity": 1.0,
                    "flashRate": 1.0,
                    "speed": 1.0,
                    "seed": 1.0,
                }
            ],
        },
        time_sec=0.0,
        kick=0.05,
        audio_env=0.0,
    )
    assert hit > miss
