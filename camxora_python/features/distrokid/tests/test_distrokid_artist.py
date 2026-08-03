"""Tests for DistroKid artist mode resolution."""

from __future__ import annotations

from features.distrokid.lib.distrokid_artist import resolve_distrokid_artist
from features.distrokid.lib.distrokid_settings import DistroKidSettings, DistroKidSettingsStore


def _context(*, primary: str = "", secondary: str = "", ok_id: str = "", alt_id: str = "") -> dict:
    return {
        "primary_artist_name": primary,
        "secondary_artist_name": secondary,
        "ok_profile_id": ok_id,
        "alt_profile_id": alt_id,
    }


def test_single_mode_uses_one_artist_for_both_roles() -> None:
    settings = DistroKidSettings(
        artist_mode="single",
        single_artist_name="Neon Collective",
        primary_artist_name="Should Ignore",
        secondary_artist_name="Also Ignore",
    )
    ctx = _context(primary="Channel A", secondary="Channel B")
    assert resolve_distrokid_artist(role="primary", settings=settings, batch_context=ctx) == "Neon Collective"
    assert resolve_distrokid_artist(role="secondary", settings=settings, batch_context=ctx) == "Neon Collective"
    assert resolve_distrokid_artist(role="alt", settings=settings, batch_context=ctx) == "Neon Collective"


def test_dual_mode_maps_roles_to_artists() -> None:
    settings = DistroKidSettings(
        artist_mode="dual",
        primary_artist_name="Artist One",
        secondary_artist_name="Artist Two",
    )
    ctx = _context(primary="Profile OK", secondary="Profile Alt")
    assert resolve_distrokid_artist(role="primary", settings=settings, batch_context=ctx) == "Artist One"
    assert resolve_distrokid_artist(role="secondary", settings=settings, batch_context=ctx) == "Artist Two"


def test_dual_mode_falls_back_to_channel_profile_names() -> None:
    settings = DistroKidSettings(artist_mode="dual")
    ctx = _context(primary="Bass Drive", secondary="Night Pulse")
    assert resolve_distrokid_artist(role="ok", settings=settings, batch_context=ctx) == "Bass Drive"
    assert resolve_distrokid_artist(role="alt", settings=settings, batch_context=ctx) == "Night Pulse"


def test_single_mode_legacy_fallback() -> None:
    settings = DistroKidSettings(artist_mode="single", artist_name="Legacy Artist")
    assert resolve_distrokid_artist(role="primary", settings=settings, batch_context=None) == "Legacy Artist"


def test_per_channel_maps_by_profile_id() -> None:
    settings = DistroKidSettings(
        artist_mode="per_channel",
        channel_artists={
            "p1": "Artist Alpha",
            "p2": "Artist Alpha",
            "p3": "Artist Beta",
            "p4": "Artist Beta",
        },
    )
    ctx = _context(primary="Channel A", secondary="Channel B", ok_id="p1", alt_id="p3")
    assert (
        resolve_distrokid_artist(
            role="primary",
            settings=settings,
            batch_context=ctx,
            profile_id="p1",
        )
        == "Artist Alpha"
    )
    assert (
        resolve_distrokid_artist(
            role="secondary",
            settings=settings,
            batch_context=ctx,
            profile_id="p3",
        )
        == "Artist Beta"
    )
    assert (
        resolve_distrokid_artist(
            role="primary",
            settings=settings,
            batch_context=ctx,
            profile_id="p2",
        )
        == "Artist Alpha"
    )


def test_per_channel_uses_batch_profile_ids_when_missing_explicit() -> None:
    settings = DistroKidSettings(
        artist_mode="per_channel",
        channel_artists={"ok-1": "Shared A", "alt-1": "Shared B"},
    )
    ctx = _context(ok_id="ok-1", alt_id="alt-1", primary="Fallback OK", secondary="Fallback Alt")
    assert resolve_distrokid_artist(role="primary", settings=settings, batch_context=ctx) == "Shared A"
    assert resolve_distrokid_artist(role="secondary", settings=settings, batch_context=ctx) == "Shared B"


def test_settings_store_persists_channel_artists(tmp_path) -> None:
    path = tmp_path / "settings.json"
    store = DistroKidSettingsStore(path=path)
    settings = DistroKidSettings(
        artist_mode="per_channel",
        channel_artists={"a": "One", "b": "Two"},
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.artist_mode == "per_channel"
    assert loaded.channel_artists == {"a": "One", "b": "Two"}
