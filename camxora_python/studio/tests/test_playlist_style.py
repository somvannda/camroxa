from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_style import apply_style_to_settings, default_sub_template_for, resolve_playlist_colors
from studio.core.playlist_sub_templates import PLAYLIST_SUB_TEMPLATES, SUB_TEMPLATES_BY_ID
from studio.ui.music.playlist_presets import PLAYLIST_PRESETS


def test_resolve_playlist_colors_uses_sub_template():
    settings = PlaylistSettings(sub_template_id="cyberpunk", color_filter_id="original")
    colors = resolve_playlist_colors(settings)
    sub = SUB_TEMPLATES_BY_ID["cyberpunk"]
    assert colors["accent"] == sub.colors["accent"]
    assert colors["bg_from"] == sub.colors["bg_from"]


def test_color_filter_applies_full_forest_mist_palette():
    settings = PlaylistSettings(sub_template_id="forest-mist", color_filter_id="neon-green")
    colors = resolve_playlist_colors(settings)
    assert colors["text"] == "#14532d"
    assert colors["accent"] == "#22c55e"
    assert colors["play_icon"] == "#22c55e"
    assert colors["surface"].endswith("28") or len(colors["surface"]) == 9


def test_forest_mist_original_uses_template_palette():
    settings = PlaylistSettings(sub_template_id="forest-mist", color_filter_id="original")
    colors = resolve_playlist_colors(settings)
    assert colors["text"] == "#ffffff"
    assert colors["accent"] == "#a2d149"
    assert colors.get("frame_border")


def test_color_filter_applies_full_minimal_white_palette():
    settings = PlaylistSettings(sub_template_id="minimal-white", color_filter_id="rose-gold")
    colors = resolve_playlist_colors(settings)
    assert colors["bg_from"] == "#fde8f0"
    assert colors["surface"] == "#fffafb"
    assert colors["text"] == "#4a1d35"
    assert colors["muted"] == "#b07a96"
    assert colors["selected_row"] == "#fce7f3"


def test_twenty_four_palette_sets_each_have_five_colors():
    from core.playlist_color_filters import PLAYLIST_COLOR_FILTERS
    from core.playlist_palette import PALETTE_SLOT_COUNT

    assert len(PLAYLIST_COLOR_FILTERS) == 24
    for filt in PLAYLIST_COLOR_FILTERS:
        assert len(filt.palette) == PALETTE_SLOT_COUNT
        for slot in filt.palette:
            assert slot.startswith("#") and len(slot) in (7, 9)


def test_apply_style_to_settings_preserves_layout_sliders():
    settings = PlaylistSettings(
        sub_template_id="retro-wave",
        corner_radius=22,
        list_row_gap=18,
    )
    apply_style_to_settings(settings)
    assert settings.corner_radius == 22
    assert settings.list_row_gap == 18
    assert settings.colors["accent"] == SUB_TEMPLATES_BY_ID["retro-wave"].colors["accent"]


def test_custom_minimal_white_color_persisted():
    from core.playlist_palette import apply_palette_slot

    settings = PlaylistSettings(sub_template_id="minimal-white", color_filter_id="original")
    apply_style_to_settings(settings)
    settings.colors = apply_palette_slot(settings.colors, "text", "#112233")
    settings.color_filter_id = "custom"
    apply_style_to_settings(settings)
    assert settings.colors["text"] == "#112233"
    assert settings.colors["play_icon"] == "#112233"
    assert settings.color_filter_id == "custom"


def test_apply_palette_slot_updates_surface():
    from core.playlist_palette import apply_palette_slot

    settings = PlaylistSettings(sub_template_id="minimal-white", color_filter_id="original")
    apply_style_to_settings(settings)
    updated = apply_palette_slot(settings.colors, "surface", "#abcdef")
    assert updated["surface"] == "#abcdef"
    assert updated["text"] == settings.colors["text"]


def test_default_sub_for_every_preset():
    for preset in PLAYLIST_PRESETS:
        sub_id = default_sub_template_for(preset.id)
        assert sub_id in SUB_TEMPLATES_BY_ID


def test_forest_mist_sub_template_layout():
    forest = SUB_TEMPLATES_BY_ID["forest-mist"]
    assert forest.name == "Forest Mist"
    assert forest.layout_style == "forest_mist"
    assert forest.glass is True
    assert forest.corner_radius == 30
    assert forest.colors["accent"] == "#a2d149"


def test_draw_forest_mist_track_list():
    import numpy as np

    from core.models import MediaAsset
    from render.playlist_forest_mist import draw_forest_mist_track_list

    state = __import__("core.project_state", fromlist=["ProjectState"]).ProjectState()
    for i, (title, artist) in enumerate(
        [
            ("Drizzle", "HEIZE"),
            ("Rainy Day", "TAEYEON"),
            ("When the Rain Stops", "JAEHYUN"),
        ]
    ):
        state.add_media(
            MediaAsset(
                id=f"m{i}",
                name=f"{title} - {artist}",
                type="audio",
                path=f"x{i}.wav",
                duration=240.0 + i * 10,
            )
        )
    settings = PlaylistSettings(
        template_id="forest-mist",
        sub_template_id="forest-mist",
        song_ids=["m0", "m1", "m2"],
        colors=SUB_TEMPLATES_BY_ID["forest-mist"].colors,
        corner_radius=30,
    )
    canvas = np.full((720, 1280, 3), 20, dtype=np.uint8)
    draw_forest_mist_track_list(
        canvas,
        (860, 40, 380, 650),
        settings=settings,
        project_state=state,
        current_index=2,
        local_time=62.0,
        playback_time=62.0,
        band_values=None,
        colors=settings.colors,
        radius=30,
        font_fn=lambda s: __import__("core.playlist_fonts", fromlist=["playlist_font"]).playlist_font("Segoe UI", s),
        canvas_w=1280,
        canvas_h=720,
    )
    assert canvas.mean() > 15


def test_ten_sub_templates():
    assert len(PLAYLIST_SUB_TEMPLATES) == 10
    assert "forest-mist" in SUB_TEMPLATES_BY_ID
    assert "soft-pastel" not in SUB_TEMPLATES_BY_ID
    forest = SUB_TEMPLATES_BY_ID["forest-mist"]
    assert forest.name == "Forest Mist"
    assert forest.layout_style == "forest_mist"


def test_forest_mist_uses_standalone_track_list_layout():
    from core.playlist_layout import is_forest_mist_layout, is_standalone_track_list_layout, resolve_component_layout

    settings = PlaylistSettings(sub_template_id="forest-mist", song_ids=["a"])
    assert is_forest_mist_layout(settings)
    assert is_standalone_track_list_layout(settings)
    layout = resolve_component_layout(settings, canvas_w=1280, canvas_h=720)
    assert "song_list" in layout
    assert "cover" not in layout


def test_minimal_white_uses_reference_layout():
    sub = SUB_TEMPLATES_BY_ID["minimal-white"]
    assert sub.layout_style == "minimal_white"
    assert sub.corner_radius == 28
    assert sub.colors["surface"] == "#ffffff"


def test_draw_minimal_white_track_list():
    import numpy as np

    from core.models import MediaAsset
    from render.playlist_minimal_white import draw_minimal_white_track_list

    state = __import__("core.project_state", fromlist=["ProjectState"]).ProjectState()
    media = MediaAsset(id="m1", name="When the Rain Stops - JAEHYUN", type="audio", path="x.wav", duration=248.0)
    state.add_media(media)
    settings = PlaylistSettings(
        template_id="vol-collection",
        sub_template_id="minimal-white",
        song_ids=["m1"],
        colors=SUB_TEMPLATES_BY_ID["minimal-white"].colors,
        corner_radius=28,
    )
    canvas = np.full((240, 320, 3), 240, dtype=np.uint8)
    draw_minimal_white_track_list(
        canvas,
        (20, 20, 280, 200),
        settings=settings,
        project_state=state,
        current_index=0,
        local_time=12.5,
        playback_time=12.5,
        band_values=None,
        colors=settings.colors,
        radius=28,
        font_fn=lambda s: __import__("core.playlist_fonts", fromlist=["playlist_font"]).playlist_font("Segoe UI", s),
        canvas_w=320,
        canvas_h=240,
    )
    assert canvas.mean() > 200


def test_clean_track_title_strips_leading_number():
    from render.playlist_minimal_white import _clean_track_title

    assert _clean_track_title("10. Blueprints Break.mp3") == "Blueprints Break"
    assert _clean_track_title("9 - Blue Hour Echoes.wav") == "Blue Hour Echoes"


def test_scaled_font_never_upscales():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_W
    from core.playlist_fonts import playlist_font_fn
    from render.playlist_minimal_white import _scaled_font

    font_fn = playlist_font_fn("Segoe UI")
    small = _scaled_font(font_fn, 15, 280)
    large = _scaled_font(font_fn, 15, MINIMAL_WHITE_REF_CARD_W * 2)
    assert large.size == 15
    assert small.size <= large.size


def test_minimal_white_layout_fits_ten_songs():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import _layout_metrics

    settings = PlaylistSettings(song_ids=[f"s{i}" for i in range(10)])
    apply_style_to_settings(settings)
    metrics = _layout_metrics(MINIMAL_WHITE_REF_CARD_W, MINIMAL_WHITE_REF_CARD_H, settings, settings.typography)
    assert metrics["max_rows"] >= 10
    assert metrics["row_h"] >= 26


def test_more_songs_compress_vertical_spacing():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import _layout_metrics

    apply_style_to_settings(PlaylistSettings())
    typo = PlaylistSettings().typography
    few = _layout_metrics(
        MINIMAL_WHITE_REF_CARD_W,
        MINIMAL_WHITE_REF_CARD_H,
        PlaylistSettings(song_ids=["a", "b", "c"]),
        typo,
    )
    many = _layout_metrics(
        MINIMAL_WHITE_REF_CARD_W,
        MINIMAL_WHITE_REF_CARD_H,
        PlaylistSettings(song_ids=[f"s{i}" for i in range(10)]),
        typo,
    )
    assert many["row_h"] <= few["row_h"]
    assert few["row_h"] >= many["row_h"]
    assert many["max_rows"] >= 10


def test_list_row_gap_applies_to_minimal_white_layout():
    from render.playlist_minimal_white import _plan_track_list_layout

    settings = PlaylistSettings(song_ids=[f"s{i}" for i in range(10)], list_row_gap=16)
    plan = _plan_track_list_layout(380, settings, settings.typography)
    assert plan["row_gap"] == 16


def test_list_row_gap_applies_to_forest_mist_layout():
    from render.playlist_forest_mist import _plan_forest_layout

    settings = PlaylistSettings(song_ids=[f"s{i}" for i in range(6)], list_row_gap=20)
    plan = _plan_forest_layout(380, settings, settings.typography)
    assert plan["row_gap"] == 20


def test_forest_mist_empty_playlist_uses_full_card_height():
    from core.playlist_layout import _minimal_white_card_size_norm
    from render.playlist_forest_mist import _plan_forest_layout, forest_mist_card_height
    from render.playlist_minimal_white import minimal_white_card_height

    typo = PlaylistSettings().typography
    empty_forest = PlaylistSettings(sub_template_id="forest-mist", song_ids=[])
    empty_minimal = PlaylistSettings(sub_template_id="minimal-white", song_ids=[])

    plan = _plan_forest_layout(380, empty_forest, typo)
    assert plan["target_rows"] == 10
    assert plan["max_rows"] == 0
    assert plan["card_h"] >= 500

    forest_h = forest_mist_card_height(empty_forest, typo)
    minimal_h = minimal_white_card_height(empty_minimal, typo)
    assert abs(forest_h - minimal_h) <= 80

    _fw, forest_norm_h = _minimal_white_card_size_norm(1280, 720, empty_forest)
    _mw, minimal_norm_h = _minimal_white_card_size_norm(1280, 720, empty_minimal)
    assert abs(forest_norm_h - minimal_norm_h) < 0.05


def test_sub_template_styles_are_isolated():
    from core.playlist_sub_template_styles import switch_sub_template

    settings = PlaylistSettings(sub_template_id="minimal-white", list_row_gap=6, corner_radius=28)
    apply_style_to_settings(settings)

    switch_sub_template(settings, "forest-mist")
    settings.list_row_gap = 18
    settings.corner_radius = 32
    settings.typography.font_family = "Calibri"

    switch_sub_template(settings, "minimal-white")
    assert settings.list_row_gap == 6
    assert settings.corner_radius == 28
    assert settings.typography.font_family == "Segoe UI"

    switch_sub_template(settings, "forest-mist")
    assert settings.list_row_gap == 18
    assert settings.corner_radius == 32
    assert settings.typography.font_family == "Calibri"


def test_reset_sub_template_style_restores_defaults():
    from core.playlist_sub_template_styles import default_style_dict, reset_sub_template_style

    settings = PlaylistSettings(sub_template_id="forest-mist")
    apply_style_to_settings(settings)
    settings.list_row_gap = 20
    settings.corner_radius = 12
    settings.color_filter_id = "custom"

    reset_sub_template_style(settings)
    defaults = default_style_dict("forest-mist")
    assert settings.list_row_gap == defaults["list_row_gap"]
    assert settings.corner_radius == defaults["corner_radius"]
    assert settings.color_filter_id == "original"


def test_styles_by_sub_template_round_trip():
    from core.playlist_sub_template_styles import switch_sub_template

    settings = PlaylistSettings(sub_template_id="minimal-white", list_row_gap=9)
    apply_style_to_settings(settings)
    settings.background_path = "/tmp/custom-bg.png"
    switch_sub_template(settings, "forest-mist")
    settings.list_row_gap = 16
    settings.background_path = "/tmp/forest-bg.png"

    data = settings.to_dict()
    restored = PlaylistSettings.from_dict(data)
    assert restored.sub_template_id == "forest-mist"
    assert restored.list_row_gap == 16
    assert restored.background_path == "/tmp/forest-bg.png"

    switch_sub_template(restored, "minimal-white")
    assert restored.list_row_gap == 9
    assert restored.background_path == "/tmp/custom-bg.png"


def test_hex_with_alpha_percent_round_trip():
    from core.playlist_palette import hex_with_alpha_percent, rgba_alpha_percent, rgb_hex_from_color

    assert hex_with_alpha_percent("#a2d149", 0) == "#a2d14900"
    assert hex_with_alpha_percent("#a2d149", 100) == "#a2d149ff"
    assert rgba_alpha_percent("#1a3d2a66") == 40
    assert rgb_hex_from_color("#1a3d2a66") == "#1a3d2a"


def test_transparent_active_row_fill_preserved():
    from core.playlist_palette import apply_palette_slot_for_layout, expand_forest_mist_palette, expand_palette

    forest = expand_forest_mist_palette("#111111", "#222222", "#ffffff", "#888888", "#123456")
    forest = apply_palette_slot_for_layout(
        forest, "selected_row", "#a2d14900", layout_style="forest_mist"
    )
    assert forest["selected_row"] == "#a2d14900"

    minimal = expand_palette("#eeeeee", "#ffffff", "#000000", "#888888", "#f2f2f7")
    minimal = apply_palette_slot_for_layout(
        minimal, "selected_row", "#7466f100", layout_style="minimal_white"
    )
    assert minimal["selected_row"] == "#7466f100"


def test_expand_palette_includes_active_text():
    from core.playlist_palette import expand_forest_mist_palette, expand_palette

    minimal = expand_palette("#eeeeee", "#ffffff", "#000000", "#888888", "#f2f2f7")
    assert minimal["active_text"] == "#000000"

    forest = expand_forest_mist_palette("#111111", "#222222", "#ffffff", "#888888", "#123456")
    assert forest["active_text"] == forest["accent"]


def test_font_variant_normalization():
    from core.playlist_fonts import normalize_font_variant, playlist_font

    assert normalize_font_variant("bold") == "bold"
    assert normalize_font_variant("unknown") == "normal"
    font = playlist_font("Segoe UI", 14, "bold")
    assert font is not None


def test_typography_variant_persistence():
    settings = PlaylistSettings(sub_template_id="minimal-white")
    settings.typography.song_title_variant = "bold"
    settings.typography.song_meta_variant = "italic"
    blob = settings.typography.to_dict()
    restored = PlaylistSettings().typography.from_dict(blob)
    assert restored.song_title_variant == "bold"
    assert restored.song_meta_variant == "italic"


def test_forest_mist_active_row_aligns_with_inactive_text():
    from core.playlist_row_chrome import default_row_chrome_for_layout
    from core.playlist_row_layout import compute_row_layout
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (400, 80))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    chrome = default_row_chrome_for_layout("forest_mist")
    layout = compute_row_layout(
        row_x0=28,
        row_x1=360,
        row_y=10,
        row_h=46,
        chrome=chrome,
        playing=True,
        duration_label="3:45",
        draw=draw,
        meta_font=font,
        play_r=12,
        title_font=font,
        num_font=font,
        artist=None,
        inset_x=6,
    )
    assert layout.text_x == 28 + 6 + 30
    chrome.numbers.enabled = False
    layout2 = compute_row_layout(
        row_x0=28,
        row_x1=360,
        row_y=10,
        row_h=46,
        chrome=chrome,
        playing=False,
        duration_label="",
        draw=draw,
        meta_font=font,
        play_r=12,
        title_font=font,
        num_font=font,
        artist=None,
        inset_x=6,
    )
    assert layout2.text_x == 28 + 6


def test_minimal_white_card_keeps_reference_aspect():
    from core.playlist_layout import (
        MINIMAL_WHITE_CARD_ASPECT,
        _minimal_white_card_size_norm,
        _minimal_white_card_width_norm,
    )

    for canvas_w, canvas_h in ((1280, 720), (720, 1280), (960, 540)):
        norm_w, norm_h = _minimal_white_card_size_norm(canvas_w, canvas_h)
        pixel_w = norm_w * canvas_w
        pixel_h = norm_h * canvas_h
        assert abs(pixel_w - _minimal_white_card_width_norm(canvas_w, canvas_h) * canvas_w) < 2
        assert abs((pixel_w / pixel_h) - MINIMAL_WHITE_CARD_ASPECT) < 0.08 or norm_h < 0.92


def test_compact_playlist_keeps_full_card_width():
    from core.playlist_layout import _minimal_white_card_size_norm

    full_w, full_h = _minimal_white_card_size_norm(1280, 720)
    settings = PlaylistSettings(sub_template_id="minimal-white", song_ids=[f"s{i}" for i in range(5)])
    apply_style_to_settings(settings)
    compact_w, compact_h = _minimal_white_card_size_norm(1280, 720, settings)
    assert abs(compact_w - full_w) < 0.001
    assert compact_h < full_h


def test_layout_tiers_fit_all_track_counts():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import (
        _TIER_PRESETS,
        _layout_capacity_tier,
        _plan_track_list_layout,
        minimal_white_card_height,
    )

    for count in (5, 10, 15, 20):
        settings = PlaylistSettings(song_ids=[f"s{i}" for i in range(count)])
        apply_style_to_settings(settings)
        plan = _plan_track_list_layout(MINIMAL_WHITE_REF_CARD_W, settings, settings.typography)
        assert plan["max_rows"] == count
        assert plan["target_rows"] == count
        assert _layout_capacity_tier(count) == count
        tier_row_h = _TIER_PRESETS[count][0]
        assert plan["row_h"] == tier_row_h
        card_h = minimal_white_card_height(settings, settings.typography, MINIMAL_WHITE_REF_CARD_W)
        assert card_h == plan["card_h"]
        assert card_h >= plan["list_top"] + count * plan["row_h"] + (count - 1) * plan["row_gap"]


def test_layout_card_height_grows_with_track_count():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import minimal_white_card_height

    apply_style_to_settings(PlaylistSettings())
    typo = PlaylistSettings().typography
    heights = []
    for count in (5, 10, 15, 20):
        settings = PlaylistSettings(song_ids=[f"s{i}" for i in range(count)])
        heights.append(minimal_white_card_height(settings, typo, MINIMAL_WHITE_REF_CARD_W))
    assert heights[0] < heights[1] < heights[2] <= heights[3]


def test_few_songs_use_taller_rows():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import _TIER_PRESETS, _layout_metrics

    settings = PlaylistSettings(song_ids=["a", "b", "c", "d", "e"])
    apply_style_to_settings(settings)
    few = _layout_metrics(
        MINIMAL_WHITE_REF_CARD_W,
        MINIMAL_WHITE_REF_CARD_H,
        settings,
        settings.typography,
    )
    assert few["row_h"] == _TIER_PRESETS[5][0]
    assert few["target_rows"] == 5


def test_few_songs_compact_card_height():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W, _minimal_white_card_size_norm
    from render.playlist_minimal_white import minimal_white_card_height

    settings = PlaylistSettings(sub_template_id="minimal-white", song_ids=[f"s{i}" for i in range(5)])
    apply_style_to_settings(settings)
    compact = minimal_white_card_height(settings, settings.typography, MINIMAL_WHITE_REF_CARD_W)
    assert compact < MINIMAL_WHITE_REF_CARD_H
    norm_w, norm_h = _minimal_white_card_size_norm(1280, 720, settings)
    assert norm_h < 0.90


def test_few_songs_keep_reference_spacing():
    from core.playlist_layout import MINIMAL_WHITE_REF_CARD_H, MINIMAL_WHITE_REF_CARD_W
    from render.playlist_minimal_white import _REF_ROW_H, _layout_metrics

    settings = PlaylistSettings(song_ids=["a", "b", "c"])
    apply_style_to_settings(settings)
    few = _layout_metrics(
        MINIMAL_WHITE_REF_CARD_W,
        MINIMAL_WHITE_REF_CARD_H,
        settings,
        settings.typography,
    )
    assert few["row_h"] >= _REF_ROW_H
    assert few["target_rows"] == 3


def test_row_pill_box_extends_past_content_band():
    from render.playlist_minimal_white import _row_content_box, _row_pill_box

    pad_x, w, row_y, row_h, row_gap = 28, 380, 120, 46, 8
    cx0, cy0, cx1, cy1 = _row_content_box(pad_x, w, row_y, row_h)
    px0, py0, px1, py1 = _row_pill_box(pad_x, w, row_y, row_h, row_gap, target_rows=10)
    assert px0 < cx0
    assert px1 > cx1
    assert py0 <= cy0
    assert py1 >= cy1


def test_small_playlist_pill_does_not_extend_vertically():
    from render.playlist_minimal_white import _row_content_box, _row_pill_box

    pad_x, w, row_y, row_h, row_gap = 28, 380, 120, 46, 8
    _, cy0, _, cy1 = _row_content_box(pad_x, w, row_y, row_h)
    _, py0, _, py1 = _row_pill_box(pad_x, w, row_y, row_h, row_gap, target_rows=3)
    assert py0 == cy0
    assert py1 == cy1


def test_row_text_layout_centers_single_line_rows():
    from core.playlist_fonts import playlist_font
    from render.playlist_minimal_white import _row_text_layout

    title_font = playlist_font("Segoe UI", 13)
    meta_font = playlist_font("Segoe UI", 11)
    num_font = playlist_font("Segoe UI", 11)
    row_y, row_h = 100, 46
    layout = _row_text_layout(
        row_y,
        row_h,
        title_font=title_font,
        meta_font=meta_font,
        num_font=num_font,
        artist=None,
    )
    title_y = layout["title_y"]
    num_y = layout["num_y"]
    dur_y = layout["dur_y"]
    row_mid = row_y + row_h / 2
    for y, font in ((title_y, title_font), (num_y, num_font), (dur_y, meta_font)):
        ascent, descent = font.getmetrics()
        text_mid = y + (ascent + descent) / 2
        assert abs(text_mid - row_mid) < 4


def test_active_row_wipes_static_text_before_drawing():
    """Regression: cached static row text must not show through the playing overlay."""
    import numpy as np

    from core.models import MediaAsset
    from core.playlist_settings import PlaylistSettings
    from core.playlist_sub_templates import SUB_TEMPLATES_BY_ID
    from core.playlist_fonts import playlist_font_fn
    from render.playlist_minimal_white import _draw_active_row_cv2, _layout_metrics

    font_fn = playlist_font_fn("Segoe UI")

    settings = PlaylistSettings(
        sub_template_id="minimal-white",
        song_ids=["m1"],
        colors=SUB_TEMPLATES_BY_ID["minimal-white"].colors,
        corner_radius=28,
    )
    media = MediaAsset(id="m1", name="06. Moonrise Jetstream Strikes_OK", type="audio", path="x.wav", duration=92.0)
    w, h = 380, 650
    metrics = _layout_metrics(w, h, settings, settings.typography)
    row_y = metrics["list_top"]
    row_h = metrics["row_h"]

    card = np.full((h, w, 4), 255, dtype=np.uint8)
    card[:, :, :3] = 255
    # Simulate static-layer text smear in the active row band.
    card[row_y : row_y + row_h, metrics["pad_x"] : w - metrics["pad_x"], :3] = 40

    _draw_active_row_cv2(
        card,
        row_y=row_y,
        row_h=row_h,
        row_gap=metrics["row_gap"],
        pad_x=metrics["pad_x"],
        w=w,
        settings=settings,
        media=media,
        row_index=0,
        local_time=62.0,
        bar_heights=(0.5, 0.8, 0.6, 0.9),
        colors=settings.colors,
        radius=28,
        font_fn=font_fn,
        typo=settings.typography,
    )

    row_band = card[row_y : row_y + row_h, metrics["pad_x"] : w - metrics["pad_x"], :3]
    static_pixels = np.all(row_band == 40, axis=2).sum()
    assert static_pixels / row_band.shape[0] / row_band.shape[1] < 0.001


def test_playlist_settings_sub_template_round_trip():
    settings = PlaylistSettings(
        template_id="glass-romance",
        sub_template_id="ocean-breeze",
        color_filter_id="mint",
    )
    restored = PlaylistSettings.from_dict(settings.to_dict())
    assert restored.sub_template_id == "ocean-breeze"
    assert restored.color_filter_id == "mint"


def test_playlist_typography_font_family_round_trip():
    from core.playlist_settings import PlaylistTypography

    typo = PlaylistTypography(font_family="Georgia", album_title_size=32)
    restored = PlaylistTypography.from_dict(typo.to_dict())
    assert restored.font_family == "Georgia"
    assert restored.album_title_size == 32


def test_resolve_playlist_font_path_finds_segoe_on_windows():
    import sys

    from core.playlist_fonts import normalize_font_family, resolve_playlist_font_path

    assert normalize_font_family("segoe-ui") == "Segoe UI"
    assert normalize_font_family("Georgia") == "Georgia"
    if sys.platform == "win32":
        assert resolve_playlist_font_path("Segoe UI") is not None
