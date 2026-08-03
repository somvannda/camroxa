"""Playlist Phase 1 — rename, looks, fonts, panel chrome."""

from __future__ import annotations

from pathlib import Path

from features.video.lib.system_fonts import (
    BUILTIN_FONT_FILES,
    clear_font_caches,
    resolve_font_file,
)
from features.video.lib.text_domain_registry import (
    PLAYLIST_LOOK_PRESET_OPTIONS,
    build_playlist_look_draft_patch,
    default_title_text_settings,
    normalize_title_text_settings,
    title_settings_from_draft,
)
from features.video.lib.text_domain_runtime import expand_text_domains_to_overlays
from features.video.widgets.right_rail import VideoRightRail


def test_neon_glass_pro_is_first_look_option() -> None:
    assert PLAYLIST_LOOK_PRESET_OPTIONS[0][0] == "purple_neon_glowing"
    assert "Neon Glass Pro" in PLAYLIST_LOOK_PRESET_OPTIONS[0][1]


def test_sample_panel_backdrop_rgba_smoke(tmp_path) -> None:
    from PIL import Image

    from features.video.lib.playlist_glass_backdrop import sample_panel_backdrop_rgba

    path = tmp_path / "bg.png"
    Image.new("RGB", (640, 360), (20, 40, 80)).save(path)
    crop = sample_panel_backdrop_rgba(str(path), panel_w=120, panel_h=80, blur_radius=8)
    assert crop is not None
    assert crop.shape == (80, 120, 4)


def test_normalize_renderer_keeps_playlist_panel_overlays() -> None:
    """Regression: preview normalize used to strip overlayKind/panel* and drop the glass plate."""
    from features.video.lib.text_domain_registry import build_playlist_look_draft_patch, title_settings_from_draft
    from features.video.lib.text_domain_runtime import expand_text_domains_to_overlays
    from visualizer.template_runtime import normalize_renderer_template

    patch = build_playlist_look_draft_patch("purple_neon_glowing")
    assert patch is not None
    settings = title_settings_from_draft(
        {
            **patch,
            "titleEnabled": True,
            "titleContentMode": "manual",
            "titleManualTitles": ["Steel Fists", "One Heartbeat"],
            "titleListActiveIndex": 0,
        }
    )
    raw_overlays = expand_text_domains_to_overlays(
        {"titleText": settings, "albumText": {"enabled": False}},
        track_paths=[],
    )
    assert any(item.get("overlayKind") == "panel" for item in raw_overlays)
    normalized = normalize_renderer_template({"textOverlays": raw_overlays})
    out = normalized.get("textOverlays") or []
    panels = [item for item in out if item.get("overlayKind") == "panel"]
    assert panels, "glass card panel must survive normalize_renderer_template"
    assert float(panels[0].get("panelWidth") or 0) > 100
    assert float(panels[0].get("opacity") or 0) >= 0.75
    titles = [item for item in out if item.get("text") == "One Heartbeat"]
    assert titles and str(titles[0].get("color") or "").lower() in {"#ffffff", "#fff"}
    active = [item for item in out if item.get("text") == "Steel Fists"]
    assert active and str(active[0].get("color") or "").lower() in {"#ffffff", "#fff"}
    plate = next(item for item in out if item.get("source") == "titleTextActivePlate")
    assert str(plate.get("panelFillMode") or "") == "gradient"


def test_list_card_honors_list_color_and_panel_opacity() -> None:
    from features.video.lib.playlist_list_card import build_playlist_list_card_overlays

    overlays = build_playlist_list_card_overlays(
        title={
            "listColor": "#ff00aa",
            "listActiveColor": "#00ffcc",
            "panelOpacity": 0.95,
            "panelFrost": 0.2,
            "panelBorderWidth": 3.0,
            "panelBorderColor": "#ff00aa",
            "panelFill": "#110022",
            "tracklistHeader": True,
            "activeRowPlate": True,
            "style": {"x": 10, "y": 10, "boxWidth": 280, "fontSize": 12, "color": "#ffffff", "glow": 0.5},
        },
        titles=["Alpha", "Beta"],
        active_index=0,
        album_name="Demo",
    )
    panel = next(item for item in overlays if item.get("source") == "titleTextPanel")
    assert abs(float(panel["opacity"]) - 0.95) < 1e-6
    assert panel["color"] == "#110022"
    assert any(item.get("text") == "Alpha" and item.get("color") == "#00ffcc" for item in overlays)
    assert any(item.get("text") == "Beta" and item.get("color") == "#ff00aa" for item in overlays)


def test_right_rail_tab_label_is_playlist() -> None:
    labels = [label for _key, label in VideoRightRail._SIDE_TABS]
    assert "Playlist" in labels
    assert "Title" not in labels


def test_playlist_look_presets_are_seven() -> None:
    assert len(PLAYLIST_LOOK_PRESET_OPTIONS) == 7
    keys = {key for key, _ in PLAYLIST_LOOK_PRESET_OPTIONS}
    assert keys == {
        "split_stage",
        "glass_aurora",
        "neon_spectrum",
        "purple_neon_glowing",
        "retro_vinyl",
        "noir_press",
        "gold_lacquer",
    }


def test_purple_neon_glowing_look_emits_tracklist_chrome() -> None:
    from features.video.lib.text_domain_registry import title_settings_from_draft

    patch = build_playlist_look_draft_patch("purple_neon_glowing")
    assert patch is not None
    assert patch["titlePlaylistLook"] == "purple_neon_glowing"
    assert patch["titleLayout"] == "list_card"
    assert patch["titleTracklistHeader"] is True
    assert patch["titleActiveRowPlate"] is True
    assert float(patch["titlePanelBorderWidth"]) >= 0.5
    assert float(patch["titlePanelFrost"]) >= 0.5
    assert float(patch["titlePanelOpacity"]) >= 0.75
    assert str(patch.get("titleStylePreset") or "") == "soft_glow"
    assert str(patch["titleListColor"]).lower() in {"#ffffff", "#fff"}
    assert str(patch["titlePanelBorderColor"]).lower() in {"#ffffff", "#fff"}
    settings = title_settings_from_draft(
        {
            **patch,
            "titleEnabled": True,
            "titleContentMode": "manual",
            "titleManualTitles": ["Sweetest Goodbye", "Break Me Clean", "A Thousand Miles"],
            "titleListActiveIndex": 0,
        }
    )
    overlays = expand_text_domains_to_overlays(
        {"titleText": settings, "albumText": {"enabled": True, "contentMode": "manual", "manualText": "Rocky Walker"}},
        track_paths=[],
    )
    sources = {str(item.get("source") or "") for item in overlays}
    assert "titleTextPanel" in sources
    assert "titleTextHeader" in sources
    assert "titleTextActivePlate" in sources
    assert "titleTextStageOuter" not in sources
    header = next(item for item in overlays if item.get("source") == "titleTextHeader")
    assert header.get("text") == "PLAYLIST"
    assert any(str(item.get("text") or "").endswith("TRACKS") for item in overlays)
    assert any(str(item.get("text") or "") == "♡" for item in overlays)
    active_plate = next(item for item in overlays if item.get("source") == "titleTextActivePlate")
    assert str(active_plate.get("panelFillMode") or "") == "gradient"
    assert float(active_plate.get("panelOuterGlow") or 0) > 0.5
    # Active row uses equalizer glyph; inactive has index numbers.
    assert any(str(item.get("text") or "") == "▍" for item in overlays)
    assert any(str(item.get("text") or "") == "Sweetest Goodbye" for item in overlays)
    assert any("Rocky" in str(item.get("text") or "") for item in overlays)


def test_playlist_list_card_bounds() -> None:
    from features.video.lib.playlist_list_card import playlist_list_card_bounds

    bounds = playlist_list_card_bounds(
        {
            "style": {"x": 100, "y": 20, "boxWidth": 280, "fontSize": 11},
        },
        ["A", "B", "C"],
    )
    assert bounds["x"] == 100
    assert bounds["contentWidth"] == 280
    assert bounds["contentHeight"] > 80


def test_playlist_look_draft_patch_sets_layout_and_fonts() -> None:
    patch = build_playlist_look_draft_patch("glass_aurora")
    assert patch is not None
    assert patch["titleLayout"] == "glass_card"
    assert patch["titleFontFamily"] == "inter"
    assert patch["titleNowPlayingEnabled"] is True
    assert float(patch["titlePanelFrost"]) >= 0.5


def test_normalize_keeps_playlist_chrome_fields() -> None:
    raw = default_title_text_settings()
    raw.update(
        {
            "layout": "split",
            "showDurations": True,
            "nowPlayingPill": True,
            "trackCountBadge": True,
            "playlistLook": "neon_spectrum",
            "panelOpacity": 0.5,
            "panelFrost": 0.6,
            "panelBorderColor": "#ff00ff",
        }
    )
    out = normalize_title_text_settings(raw)
    assert out["layout"] == "split"
    assert out["showDurations"] is True
    assert out["nowPlayingPill"] is True
    assert out["trackCountBadge"] is True
    assert out["playlistLook"] == "neon_spectrum"
    assert out["panelBorderColor"].lower() == "#ff00ff"


def test_title_settings_from_draft_roundtrip_playlist_fields() -> None:
    draft = {
        "titleEnabled": True,
        "titleLayout": "vinyl",
        "titleShowDurations": True,
        "titleNowPlayingEnabled": True,
        "titleTrackCountBadge": True,
        "titlePlaylistLook": "retro_vinyl",
        "titlePanelOpacity": 0.48,
        "titlePanelFrost": 0.25,
        "titlePanelBorderWidth": 2.0,
        "titlePanelBorderColor": "#f472b6",
        "titlePanelSpecular": 0.4,
        "titlePanelFill": "#1a1025",
        "titleFontFamily": "montserrat",
        "titleFontSize": 12.0,
    }
    settings = title_settings_from_draft(draft)
    assert settings["layout"] == "vinyl"
    assert settings["playlistLook"] == "retro_vinyl"
    assert settings["trackCountBadge"] is True
    assert abs(float(settings["panelOpacity"]) - 0.48) < 1e-6


def test_expand_adds_track_count_badge_when_enabled() -> None:
    tpl = {
        "titleText": {
            "enabled": True,
            "contentMode": "manual",
            "manualTitles": ["One", "Two", "Three"],
            "trackCountBadge": True,
            "nowPlayingEnabled": True,
            "listActiveIndex": 0,
            "layout": "column",
            "style": {"fontSize": 12, "x": 100, "y": 0, "boxWidth": 280, "fontFamily": "inter"},
        }
    }
    overlays = expand_text_domains_to_overlays(tpl, track_paths=[])
    sources = [str(item.get("source") or "") for item in overlays]
    assert "titleTextBadge" in sources
    badge = next(item for item in overlays if item.get("source") == "titleTextBadge")
    assert badge.get("text") == "3"


def test_expand_adds_glass_panel_and_now_playing_pill() -> None:
    tpl = {
        "titleText": {
            "enabled": True,
            "contentMode": "manual",
            "manualTitles": ["Steel Fists", "One Heartbeat"],
            "nowPlayingEnabled": True,
            "nowPlayingPill": True,
            "listActiveIndex": 0,
            "listActiveColor": "#22d3ee",
            "layout": "split",
            "panelOpacity": 0.5,
            "panelFrost": 0.4,
            "panelBorderWidth": 1.5,
            "panelBorderColor": "#ff00ff",
            "panelSpecular": 0.65,
            "panelFill": "#0a0e27",
            "style": {"fontSize": 12, "x": 400, "y": -30, "boxWidth": 330, "fontFamily": "montserrat"},
        }
    }
    overlays = expand_text_domains_to_overlays(tpl, track_paths=[])
    kinds = {str(item.get("overlayKind") or "text") for item in overlays}
    sources = [str(item.get("source") or "") for item in overlays]
    assert "panel" in kinds
    assert "pill" in kinds
    assert "titleTextPanel" in sources
    assert "titleTextPill" in sources
    panel = next(item for item in overlays if item.get("source") == "titleTextPanel")
    assert float(panel.get("panelWidth") or 0) > 100
    assert float(panel.get("panelHeight") or 0) > 20
    pill = next(item for item in overlays if item.get("source") == "titleTextPill")
    assert pill.get("text") == "NOW PLAYING"
    # Active row must not use the old ▶ prefix when a real pill exists.
    rows = [item for item in overlays if item.get("source") == "titleText"]
    assert rows and not str(rows[0].get("text") or "").startswith("▶")


def test_layout_side_patch_snaps_split_positions() -> None:
    from features.video.lib.text_domain_registry import build_playlist_layout_side_draft_patch

    right = build_playlist_layout_side_draft_patch("split")
    left = build_playlist_layout_side_draft_patch("split_left")
    assert right["titleLayout"] == "split"
    assert float(right["titleX"]) > 0
    assert left["titleLayout"] == "split_left"
    assert float(left["titleX"]) < 0


def test_render_panel_rgba_smoke() -> None:
    from visualizer.gpu_render import _render_panel_rgba

    arr, w, h = _render_panel_rgba(
        200,
        120,
        fill="#0a0e27",
        opacity=0.5,
        border_color="#ff00ff",
        border_width=2.0,
        radius=14.0,
        frost=0.4,
        specular=0.65,
    )
    assert w >= 200 and h >= 120
    assert arr.shape[2] == 4
    assert int(arr[..., 3].max()) > 0


def test_bundled_ofl_fonts_resolve() -> None:
    clear_font_caches()
    for key in ("inter", "montserrat", "rajdhani", "playfair", "bebasneue", "sourceserif"):
        rel = BUILTIN_FONT_FILES[key]
        assert "/" in rel
        path = resolve_font_file(key)
        assert Path(path).is_file(), f"{key} -> {path}"
