"""Merged-file discovery used by the Progress Upload action."""

from __future__ import annotations

import os
import time
from pathlib import Path

from shared.lib.publish_auto import discover_merged_path


def _touch(path: Path, age_seconds: float = 0.0) -> Path:
    path.write_bytes(b"x")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_returns_empty_for_missing_or_blank_run_dir(tmp_path: Path) -> None:
    assert discover_merged_path("") == ""
    assert discover_merged_path(None) == ""
    assert discover_merged_path(str(tmp_path / "missing")) == ""


def test_prefers_the_newest_long_merge_and_ignores_reels(tmp_path: Path) -> None:
    _touch(tmp_path / "MERGED_OK_old.mp4", age_seconds=120)
    newest = _touch(tmp_path / "MERGED_OK_new.mp4", age_seconds=5)
    _touch(tmp_path / "MERGED_REEL_OK_new.mp4", age_seconds=0)

    assert discover_merged_path(str(tmp_path)) == str(newest)


def test_falls_back_to_the_merged_subfolder(tmp_path: Path) -> None:
    sub = tmp_path / "merged"
    sub.mkdir()
    target = _touch(sub / "MERGED_ALT_1.mp4")

    assert discover_merged_path(str(tmp_path)) == str(target)


def test_returns_empty_when_only_reels_exist(tmp_path: Path) -> None:
    _touch(tmp_path / "MERGED_REEL_OK_1.mp4")

    assert discover_merged_path(str(tmp_path)) == ""
