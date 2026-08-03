"""Tests for Windows profile locality checks (cross-machine path rejection)."""

from __future__ import annotations

from pathlib import Path

from shared.lib.path_locality import (
    current_windows_profile_name,
    is_foreign_windows_profile_path,
    windows_profile_name_from_path,
)


def test_windows_profile_name_from_path_extracts_users_segment() -> None:
    assert (
        windows_profile_name_from_path(r"C:\Users\Kong Somvannda\AppData\Local\Camxora\Media")
        == "Kong Somvannda"
    )
    assert windows_profile_name_from_path(r"C:/Users/PC/Downloads/SUNO") == "PC"
    assert windows_profile_name_from_path(r"D:\Music\Album") is None
    assert windows_profile_name_from_path(r"E:\SUNO\bass-drive") is None
    assert windows_profile_name_from_path("") is None


def test_is_foreign_windows_profile_path_detects_other_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.lib.path_locality.current_windows_profile_name",
        lambda: "PC",
    )
    monkeypatch.setattr("shared.lib.path_locality.os.name", "nt")

    assert is_foreign_windows_profile_path(
        r"C:\Users\Kong Somvannda\AppData\Local\Camxora\Media\Downloads"
    )
    assert not is_foreign_windows_profile_path(r"C:\Users\PC\AppData\Local\Camxora\Media\Downloads")
    assert not is_foreign_windows_profile_path(r"C:\Users\Public\Shared\Music")
    assert not is_foreign_windows_profile_path(r"D:\NewDrive\bass-drive\album")
    assert not is_foreign_windows_profile_path(r"E:\SUNO")


def test_current_windows_profile_name_reads_userprofile(monkeypatch, tmp_path: Path) -> None:
    profile = tmp_path / "FakeUser"
    profile.mkdir()
    monkeypatch.setenv("USERPROFILE", str(profile))
    assert current_windows_profile_name() == "FakeUser"
