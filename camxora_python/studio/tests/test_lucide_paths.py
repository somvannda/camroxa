from studio.ui.icons.lucide_paths import (
    lucide_filled_polygon_points,
    play_circle_radius_for_row,
    play_icon_height_for_circle,
)


def test_play_icon_height_matches_diameter_ratio():
    r = play_circle_radius_for_row(46)
    icon_h = play_icon_height_for_circle(r)
    assert icon_h <= r * 2 * 0.25
    assert icon_h >= 4


def test_lucide_play_polygon_is_centered():
    pts = lucide_filled_polygon_points("play", 50.0, 40.0, height_px=12.0)
    assert len(pts) == 3
    cx = sum(p[0] for p in pts) / 3
    cy = sum(p[1] for p in pts) / 3
    assert abs(cx - 50.0) < 2.5
    assert abs(cy - 40.0) < 1.0
