"""Smoke tests for text styles + background color grading plan."""

from __future__ import annotations

import pytest

from features.video.lib.effect_pack_draft_state import build_applied_effect_pack_draft_state
from features.video.lib.text_color_engine import extract_text_color_model, normalize_text_fill_mode
from features.video.lib.text_domain_registry import (
    TEXT_DOMAIN_PRESET_OPTIONS,
    album_settings_from_draft,
    resolve_text_domain_preset_style,
    title_settings_from_draft,
)
from features.video.lib.text_domain_runtime import expand_text_domains_to_overlays
from features.video.lib.video_template_draft import build_background_settings_state
from features.video.lib.video_template_save import build_background_template_patch
from visualizer.gpu_render import _render_text_rgba
from visualizer.template_runtime import normalize_renderer_template


def test_ten_text_presets_exist() -> None:
    ids = [key for key, _ in TEXT_DOMAIN_PRESET_OPTIONS]
    assert len(ids) == 10
    assert "neon_glow" in ids
    assert "orange_fire_3d" in ids
    assert resolve_text_domain_preset_style("album", "neon_glow") is not None
    # Old aliases still resolve.
    assert resolve_text_domain_preset_style("album", "neon_outline") is not None


def test_text_align_options_and_legacy_anchor_migration() -> None:
    from features.video.lib.text_domain_registry import TEXT_ALIGN_OPTIONS, normalize_text_style

    assert [key for key, _ in TEXT_ALIGN_OPTIONS] == ["left", "center", "right", "justify"]
    assert normalize_text_style({"align": "justify"})["align"] == "justify"
    assert normalize_text_style({"align": "justify"})["anchor"] == "top-left"
    # Old drafts stored screen anchors; migrate into text alignment.
    assert normalize_text_style({"anchor": "center"})["align"] == "center"
    assert normalize_text_style({"anchor": "top-right"})["align"] == "right"
    assert normalize_text_style({"anchor": "bottom-left"})["align"] == "left"
    # Explicit align wins over legacy anchor.
    assert normalize_text_style({"align": "left", "anchor": "center"})["align"] == "left"


def test_every_preset_has_letter_and_line_spacing() -> None:
    from features.video.lib.text_domain_registry import (
        TEXT_DOMAIN_PRESET_PATCHES,
        build_text_domain_preset_factory_style,
        style_patch_for_domain,
    )

    for preset_id, _label in TEXT_DOMAIN_PRESET_OPTIONS:
        patch = TEXT_DOMAIN_PRESET_PATCHES[preset_id]
        assert patch["letterSpacing"] == 0.0
        assert patch["lineSpacing"] == 1.2
        factory = build_text_domain_preset_factory_style(preset_id)
        assert factory is not None
        assert factory["letterSpacing"] == 0.0
        assert factory["lineSpacing"] == 1.2
        draft = style_patch_for_domain("album", factory)
        assert draft["albumLetterSpacing"] == 0.0
        assert draft["albumLineSpacing"] == 1.2


def test_resolve_poppins_bold_face() -> None:
    from pathlib import Path

    from features.video.lib.system_fonts import clear_font_caches, resolve_font_file

    clear_font_caches()
    regular = resolve_font_file("Poppins", bold=False)
    bold = resolve_font_file("Poppins", bold=True)
    # If Poppins is installed, Bold must pick a different heavier face.
    if "poppins" in Path(regular).stem.lower():
        assert "bold" in Path(bold).stem.lower() or "black" in Path(bold).stem.lower()
        assert Path(bold).name.lower() != Path(regular).name.lower()
    # Builtin Arial bold still works.
    arial_bold = resolve_font_file("arial", bold=True)
    assert "bd" in Path(arial_bold).stem.lower() or "bold" in Path(arial_bold).stem.lower()


def test_zero_stroke_and_shadow_are_preserved() -> None:
    from features.video.lib.text_domain_runtime import _style_to_overlay_fields, expand_text_domains_to_overlays

    fields = _style_to_overlay_fields(
        {
            "fontSize": 10,
            "strokeWidth": 0,
            "shadow": 0,
            "glow": 0,
            "extrudeDepth": 0,
            "letterSpacing": 0,
        }
    )
    assert fields["strokeWidth"] == 0.0
    assert fields["shadow"] == 0.0
    assert fields["glow"] == 0.0

    overlays = expand_text_domains_to_overlays(
        {
            "titleText": {
                "enabled": True,
                "contentMode": "manual",
                "manualTitles": ["Hello World"],
                "listStyle": "plain",
                "layout": "column",
                "style": {
                    "fontSize": 12,
                    "strokeWidth": 0,
                    "shadow": 0,
                    "glow": 0,
                    "boxWidth": 80,
                    "fontFamily": "arial",
                },
            }
        }
    )
    assert overlays
    assert overlays[0]["strokeWidth"] == 0.0
    assert overlays[0]["shadow"] == 0.0
    # Box width must actually wrap (glyph-measured), not leave a long single line.
    assert "\n" in str(overlays[0]["text"]) or len(str(overlays[0]["text"])) < 20


def test_wrap_text_to_box_width() -> None:
    from features.video.lib.text_domain_runtime import wrap_text_to_box_width

    wrapped = wrap_text_to_box_width(
        "Chrome Veins on the Tarmac Tide Forever",
        box_width=120,
        font_size=32,
        letter_spacing=0,
    )
    assert "\n" in wrapped
    assert wrap_text_to_box_width("Short", box_width=0, font_size=32) == "Short"


def test_capcut_box_resize_handles() -> None:
    from features.video.widgets.text_drag_overlay import compute_box_resize

    base = dict(
        press_w=200.0,
        press_h=100.0,
        press_font=40.0,
        press_letter=2.0,
        press_x=10.0,
        press_y=20.0,
        press_wrap_w=200.0,
    )
    # Left/right: wrap only — font unchanged, opposite edge fixed.
    right = compute_box_resize(edge="r", dx_tpl=50.0, dy_tpl=0.0, **base)
    assert right["boxWidth"] == 250.0
    assert right["fontSize"] == 40.0
    assert right["x"] == 10.0

    left = compute_box_resize(edge="l", dx_tpl=-40.0, dy_tpl=0.0, **base)
    assert left["boxWidth"] == 240.0
    assert left["x"] == 10.0 - 40.0  # left edge moved out → x shifts left
    assert left["fontSize"] == 40.0

    # Bottom-right corner: uniform scale of font + content + letter spacing.
    br = compute_box_resize(edge="br", dx_tpl=200.0, dy_tpl=100.0, **base)
    assert br["scale"] == pytest.approx(2.0)
    assert br["fontSize"] == pytest.approx(80.0)
    assert br["letterSpacing"] == pytest.approx(4.0)
    assert br["lineSpacing"] == pytest.approx(1.2)  # multiplier kept; pitch scales via font
    assert br["contentWidth"] == pytest.approx(400.0)
    assert br["boxWidth"] == pytest.approx(400.0)  # wrap also scales
    assert br["x"] == 10.0 and br["y"] == 20.0

    # Top-left corner keeps opposite (bottom-right) fixed.
    tl = compute_box_resize(edge="tl", dx_tpl=-100.0, dy_tpl=-50.0, **base)
    assert tl["scale"] == pytest.approx(1.5)
    assert tl["fontSize"] == pytest.approx(60.0)
    assert tl["x"] < 10.0 and tl["y"] < 20.0

    # Top/bottom: scale type from height; content width scales with font.
    top = compute_box_resize(edge="t", dx_tpl=0.0, dy_tpl=-50.0, **base)
    assert top["contentWidth"] == pytest.approx(300.0)
    assert top["fontSize"] == pytest.approx(60.0)
    assert top["y"] < 20.0


def test_title_layout_bounds_cover_both_columns() -> None:
    from features.video.lib.text_domain_runtime import measure_title_layout_bounds

    titles = [
        "Staccato Lanes of Fading Sign",
        "Frequenz",
        "Neon Boulevard",
        "Vapor Trail",
    ]
    style = {
        "fontSize": 36,
        "fontFamily": "arialbd",
        "bold": True,
        "strokeWidth": 2,
        "letterSpacing": 0,
        "lineSpacing": 1.2,
        "boxWidth": 0,
        "x": 40,
        "y": 20,
    }
    bounds = measure_title_layout_bounds(
        titles,
        list_style="number",
        layout="grid2_td",
        style=style,
        number_indent="aligned",
    )
    # Two columns → content wider than a single title cell.
    assert bounds["contentWidth"] > 280
    assert bounds["contentHeight"] > 60


def test_grid_columns_start_after_longest_title() -> None:
    from features.video.lib.text_domain_runtime import expand_text_domains_to_overlays

    template = {
        "titleText": {
            "enabled": True,
            "contentMode": "manual",
            "manualTitles": [
                "Staccato Lanes of Fading Sign",
                "Frequenz",
                "Neon Boulevard",
                "Vapor Trail",
            ],
            "listStyle": "number",
            "numberIndent": "aligned",
            "layout": "grid2_td",
            "style": {
                "anchor": "left",
                "fontSize": 36,
                "fontFamily": "arialbd",
                "bold": True,
                "strokeWidth": 2,
                "letterSpacing": 0,
                "lineSpacing": 1.2,
            },
        }
    }
    overlays = expand_text_domains_to_overlays(template)
    assert len(overlays) == 4
    # grid2_td: col0 = 0,2  col1 = 1,3
    left = [o for o in overlays if float(o["x"]) == float(overlays[0]["x"])]
    right = [o for o in overlays if float(o["x"]) > float(overlays[0]["x"])]
    assert len(left) == 2 and len(right) == 2
    # Second column must clear the longest left title (not a fixed 280 gap).
    assert float(right[0]["x"]) - float(left[0]["x"]) > 200


def test_text_color_engine_modes() -> None:
    assert normalize_text_fill_mode("gradient") == "gradient"
    model = extract_text_color_model(
        {
            "fillMode": "neon",
            "color": "#ffffff",
            "glowColor": "#ff00aa",
            "gradientColors": ["#fff", "#0ff"],
        }
    )
    assert model["fillMode"] == "neon"
    assert model["glowColor"].startswith("#")
    assert model["glowMode"] == "solid"

    glow_grad = extract_text_color_model(
        {
            "fillMode": "neon",
            "color": "#ffffff",
            "glowMode": "gradient",
            "glowColor": "#ff1a3c",
            "glowGradientColors": ["#ff1a3c", "#ff6a00"],
            "glowGradientDirection": "horizontal",
        }
    )
    assert glow_grad["glowMode"] == "gradient"
    assert len(glow_grad["glowGradientColors"]) >= 2


def test_neon_glow_gradient_render() -> None:
    """Multi-pass bloom + gradient glow should produce a bright halo."""
    arr, tw, th = _render_text_rgba(
        "2:17AM",
        64.0,
        "#ffffff",
        "#000000",
        0.0,
        0.0,
        fill_mode="neon",
        glow=0.9,
        glow_color="#ff1a3c",
        glow_blur=16.0,
        glow_mode="gradient",
        glow_gradient_colors=["#ff1a3c", "#ff6a00"],
        glow_gradient_direction="horizontal",
    )
    assert tw > 20 and th > 20
    # Halo expands beyond glyph box — texture should be larger than bare text.
    assert tw > 120
    alpha = arr[:, :, 3]
    assert int((alpha > 0).sum()) > 800
    # Neon core should push some pixels toward bright red/white.
    lit = arr[alpha > 40]
    assert lit.size > 0
    assert float(lit[:, 0].mean()) > 80.0  # red channel present in glow


def test_legacy_text_overlays_are_not_expanded() -> None:
    template = {
        "textOverlays": [
            {
                "enabled": True,
                "text": "Old Animated Text",
                "animation": "fade",
                "startSec": 0,
                "durationSec": 4,
            }
        ],
        "albumText": {"enabled": False},
        "titleText": {"enabled": False},
    }
    assert expand_text_domains_to_overlays(template) == []


def test_title_list_row_gap_avoids_overlap() -> None:
    template = {
        "titleText": {
            "enabled": True,
            "contentMode": "manual",
            "manualTitles": ["One", "Two", "Three"],
            "listStyle": "number",
            "numberIndent": "aligned",
            "layout": "column",
            "style": {
                "anchor": "left",
                "fontSize": 42,
                "lineSpacing": 1.2,
                "glow": 0.8,
                "glowBlur": 14,
                "strokeWidth": 2,
            },
        }
    }
    overlays = expand_text_domains_to_overlays(template)
    assert len(overlays) == 3
    assert all(str(o.get("anchor") or "").endswith("left") or "left" in str(o.get("anchor")) for o in overlays)
    ys = [float(o["y"]) for o in overlays]
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    assert all(gap > 42 for gap in gaps)
    # Same left indent for every row.
    xs = [float(o["x"]) for o in overlays]
    assert len(set(xs)) == 1


def test_title_list_active_color_expansion() -> None:
    template = {
        "titleText": {
            "enabled": True,
            "contentMode": "manual",
            "manualTitles": ["One", "Two", "Three"],
            "listStyle": "number",
            "numberIndent": "aligned",
            "layout": "column",
            "listColor": "#c4b5fd",
            "listActiveColor": "#fde047",
            "listActiveIndex": 1,
            "style": {"anchor": "left", "fontSize": 32, "color": "#ffffff"},
        }
    }
    overlays = expand_text_domains_to_overlays(template)
    titles = [o for o in overlays if o.get("source") == "titleText"]
    assert len(titles) == 3
    assert titles[0]["color"].lower() == "#c4b5fd"
    assert titles[1]["color"].lower() == "#fde047"
    assert titles[2]["color"].lower() == "#c4b5fd"


def test_title_active_follows_selected_track() -> None:
    paths = [
        r"D:/x/1. Alpha_OK.mp3",
        r"D:/x/2. Beta_Primary.mp3",
        r"D:/x/3. Gamma_Secondary.mp3",
    ]
    template = {
        "titleText": {
            "enabled": True,
            "contentMode": "pipeline",
            "listStyle": "number",
            "layout": "column",
            "listColor": "#c4b5fd",
            "listActiveColor": "#fde047",
            "listActiveIndex": 0,
            "style": {"anchor": "left", "fontSize": 32, "color": "#ffffff"},
        }
    }
    overlays = expand_text_domains_to_overlays(
        template,
        track_paths=paths,
        active_track_path=paths[1],
    )
    titles = [o for o in overlays if o.get("source") == "titleText"]
    assert len(titles) == 3
    assert titles[0]["color"].lower() == "#c4b5fd"
    assert titles[1]["color"].lower() == "#fde047"
    assert titles[2]["color"].lower() == "#c4b5fd"


def test_background_contrast_sat_hue_roundtrip() -> None:
    draft = {
        "backgroundEnabled": True,
        "backgroundFitMode": "cover",
        "backgroundUserScale": 1.0,
        "backgroundBrightness": 1.1,
        "backgroundContrast": 1.2,
        "backgroundSaturation": 0.8,
        "backgroundHue": 30,
        "backgroundReactivity": 0,
        "backgroundSmoothing": 0.8,
        "backgroundMotionMode": "none",
        "backgroundMotionZoomStrength": 1,
        "backgroundMotionVibrateStrength": 1,
        "backgroundMotionSpeed": 1,
    }
    patch = build_background_template_patch({}, draft)
    bg = patch["backgroundSettings"]
    assert bg["contrast"] == 1.2
    assert bg["saturation"] == 0.8
    assert bg["hue"] == 30
    state = build_background_settings_state({"backgroundSettings": bg})
    assert state["backgroundContrast"] == 1.2
    assert state["backgroundSaturation"] == 0.8
    assert state["backgroundHue"] == 30
    norm = normalize_renderer_template({"backgroundSettings": bg})
    assert abs(norm["backgroundSettings"]["contrast"] - 1.2) < 1e-6
    assert abs(norm["backgroundSettings"]["hue"] - 30) < 1e-6


def test_render_text_rgba_glow_and_extrude() -> None:
    arr, tw, th = _render_text_rgba(
        "Glow",
        48.0,
        "#ffffff",
        "#000000",
        2.0,
        0.3,
        glow=0.8,
        glow_color="#ff4fd8",
        glow_blur=10.0,
        extrude_depth=4,
        extrude_color="#220022",
        fill_mode="gradient",
        gradient_colors=["#ffffff", "#22d3ee"],
        gradient_direction="vertical",
        letter_spacing=1.0,
        line_spacing=1.35,
    )
    assert tw > 0 and th > 0
    assert arr is not None and arr.size > 0


def test_khmer_unicode_font_fallback_and_render() -> None:
    from pathlib import Path

    from features.video.lib.system_fonts import (
        clear_font_caches,
        font_covers_text,
        resolve_font_file,
        resolve_font_for_text,
        text_needs_complex_shaping,
    )
    from features.video.lib.text_domain_runtime import wrap_text_to_box_width

    clear_font_caches()
    khmer = "សួស្តី ពិភពលោក"
    assert text_needs_complex_shaping(khmer)
    assert not text_needs_complex_shaping("Hello World")

    arial = resolve_font_file("arial")
    assert font_covers_text(arial, "Hello") is True
    # Latin faces must not claim Khmer coverage (tofu / .notdef boxes).
    assert font_covers_text(arial, khmer) is False

    fallback = resolve_font_for_text("Poppins", khmer)
    assert font_covers_text(fallback, khmer) is True
    stem = Path(fallback).stem.lower()
    assert "khmer" in stem or "daun" in stem or "battambang" in stem

    # Complex scripts keep whole tokens (no per-codepoint hard breaks).
    wrapped = wrap_text_to_box_width(
        khmer,
        box_width=40,
        font_size=28,
        letter_spacing=4.0,
        font_family="arial",
    )
    assert "\n" in wrapped or wrapped == khmer
    assert all(len(part) > 0 for part in wrapped.split("\n") if part.strip())

    arr, tw, th = _render_text_rgba(
        khmer,
        36.0,
        "#ffffff",
        "#000000",
        0.0,
        0.0,
        font_family="Poppins",
        letter_spacing=6.0,
        align="center",
        box_width=220.0,
    )
    assert tw > 8 and th > 8
    assert int((arr[:, :, 3] > 0).sum()) > 200


def test_album_title_pack_apply_does_not_use_spectrum() -> None:
    from features.video.lib.template_draft_domains import pick_album_draft_slice, pick_title_draft_slice
    from features.video.lib.video_template_draft import build_video_template_draft

    current_template = {
        "style": "orbit-spikes",
        "spectrumEnabled": True,
        "albumText": {"enabled": False},
        "titleText": {"enabled": False},
    }
    current_draft = build_video_template_draft(current_template, logo_path="")

    album = build_applied_effect_pack_draft_state(
        current_draft=current_draft,
        current_template=current_template,
        logo_path="",
        domain="album",
        item={
            "packId": "pack.album.test",
            "version": "1.0.0",
            "templatePatch": {
                "albumText": {
                    "enabled": True,
                    "style": {"color": "#ff00aa", "fillMode": "neon"},
                },
                "style": "should-not-overwrite",
            },
        },
    )
    assert album["nextDraft"]["albumEnabled"] is True
    assert album["nextDraft"]["albumColor"].lower() == "#ff00aa"
    assert album["nextDraft"]["style"] == "orbit-spikes"
    assert album["nextDraft"]["effectPacks"]["album"] == {
        "packId": "pack.album.test",
        "version": "1.0.0",
    }
    assert album["nextLayers"] is None
    assert "albumFillMode" in pick_album_draft_slice(album["nextDraft"])

    title = build_applied_effect_pack_draft_state(
        current_draft=current_draft,
        current_template=current_template,
        logo_path="",
        domain="title",
        item={
            "packId": "pack.title.test",
            "version": "1.0.0",
            "templatePatch": {
                "titleText": {
                    "enabled": True,
                    "listColor": "#aabbcc",
                    "listActiveColor": "#fde047",
                    "listActiveIndex": 0,
                },
                "style": "should-not-overwrite",
            },
        },
    )
    assert title["nextDraft"]["titleEnabled"] is True
    assert title["nextDraft"]["titleListColor"].lower() == "#aabbcc"
    assert title["nextDraft"]["style"] == "orbit-spikes"
    assert title["nextLayers"] is None
    assert "titleListActiveIndex" in pick_title_draft_slice(title["nextDraft"])


def test_album_title_draft_settings_defaults() -> None:
    album = album_settings_from_draft({})
    title = title_settings_from_draft({})
    assert album["stylePreset"] == "neon_glow"
    assert title["stylePreset"] == "midnight_stack"
    assert "listActiveIndex" in title
    assert title["listActiveIndex"] == 0


def test_album_title_style_fields_roundtrip() -> None:
    from features.video.lib.video_template_save import build_album_template_patch, build_title_template_patch

    draft = {
        "albumEnabled": True,
        "albumStylePreset": "orange_fire_3d",
        "albumFillMode": "gradient",
        "albumGradientColors": ["#ff6b00", "#ffd700"],
        "albumGradientDirection": "vertical",
        "albumGlow": 0.7,
        "albumGlowBlur": 12,
        "albumGlowColor": "#ff4fd8",
        "albumExtrudeDepth": 5,
        "albumExtrudeColor": "#331100",
        "albumShadowBlur": 4,
        "titleEnabled": True,
        "titleStylePreset": "midnight_stack",
        "titleListColor": "#c4b5fd",
        "titleListActiveColor": "#fde047",
        "titleListActiveIndex": 2,
        "titleFillMode": "neon",
        "titleGlowColor": "#a78bfa",
    }
    album_patch = build_album_template_patch(draft)
    title_patch = build_title_template_patch(draft)
    album = album_patch["albumText"]
    title = title_patch["titleText"]
    assert album["style"]["fillMode"] == "gradient"
    assert album["style"]["glow"] == 0.7
    assert album["style"]["extrudeDepth"] == 5
    assert title["listColor"].lower() == "#c4b5fd"
    assert title["listActiveColor"].lower() == "#fde047"
    assert title["listActiveIndex"] == 2
    assert title["style"]["fillMode"] == "neon"
