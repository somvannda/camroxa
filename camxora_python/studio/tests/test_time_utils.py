from studio.core.time_utils import clamp, fmt_time, fmt_time_hms, fmt_time_ruler, snap


def test_clamp_bounds():
    assert clamp(5, 0, 10) == 5
    assert clamp(-5, 0, 10) == 0
    assert clamp(15, 0, 10) == 10


def test_snap_rounds_to_nearest_twentieth():
    assert snap(1.234) == 1.25
    assert snap(0.0) == 0.0
    assert snap(2.02) == 2.0


def test_fmt_time_formats_minutes_seconds_centiseconds():
    assert fmt_time(0) == "00:00.00"
    assert fmt_time(65.5) == "01:05.50"
    assert fmt_time(-3) == "00:00.00"


def test_fmt_time_matches_reference_examples():
    assert fmt_time(3661.23) == "61:01.23"


def test_fmt_time_hms_capcut_player_format():
    assert fmt_time_hms(0) == "00:00:00"
    assert fmt_time_hms(3661.9) == "01:01:01"
    assert fmt_time_hms(-1) == "00:00:00"


def test_fmt_time_ruler_shows_hours_when_needed():
    assert fmt_time_ruler(65.0) == "01:05"
    assert fmt_time_ruler(3661.0) == "1:01:01"
