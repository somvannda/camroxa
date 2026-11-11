"""Channel/profile mismatch detection."""

from __future__ import annotations

from features.settings.views.settings_view import SettingsView


def test_matching_names_pass() -> None:
    check = SettingsView._channel_matches_profile
    assert check("Bass Drive", "BASS DRIVE")
    assert check("Bass Prime", "Bass Prime")
    assert check("Beattok Remixes", "BEATTOK REMIXES")
    assert check("Bass Reactor", "Bass Reactor")


def test_swapped_channels_are_flagged() -> None:
    check = SettingsView._channel_matches_profile
    # The production mix-up: Bass Gravity profile connected to the Bass Prime channel.
    assert not check("Bass Gravity", "Bass Prime")
    assert not check("Bass Prime", "Bass Gravity")
    assert not check("Bass Drive", "THUNDER BASS")


def test_missing_values_do_not_warn() -> None:
    check = SettingsView._channel_matches_profile
    assert check("", "Bass Prime")
    assert check("Bass Prime", "")
