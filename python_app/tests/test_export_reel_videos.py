"""Unit tests for AutoVideoHandlersMixin._export_reel_videos."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from python_app.features.auto_video.coordinator import (
    AutoVideoChannelPlan,
    AutoVideoReelPlan,
)


# ---------- Helpers ---------- #


class _FakeBus:
    def __init__(self):
        self.music_event = MagicMock()


class _FakeExportGate:
    """Minimal export_gate stub."""
    def acquire(self):
        pass

    def release(self):
        pass

    def throttle_spawn(self):
        pass


class _FakeHandler:
    """Minimal mixin host that provides _export_reel_videos."""

    def __init__(self, *, coordinator: Any, bus: Any):
        self.auto_video_coordinator = coordinator
        self.bus = bus

    # Import the actual method from the mixin
    from python_app.app.auto_video_handlers import AutoVideoHandlersMixin
    _export_reel_videos = AutoVideoHandlersMixin._export_reel_videos


def _make_plan(output_dir: str, mp3s: list[str] | None = None) -> AutoVideoChannelPlan:
    return AutoVideoChannelPlan(
        batch_id="batch-2024-01-15-1-5",
        profile_id="prof-123",
        role="OK",
        output_dir=output_dir,
        mp3s=mp3s or [],
        bg_path="/tmp/bg.png",
        logo_path="/tmp/logo.png",
        template={"some": "template"},
        ffmpeg_path="/usr/bin/ffmpeg",
        expected_count=2,
        width=1920,
        height=1080,
        speed_mode="balanced",
        export_workers=2,
    )


# ---------- Tests ---------- #


class TestExportReelVideosSkipWhenNoReelPlan:
    """When resolve_reel_plan returns None, skip entirely."""

    def test_returns_empty_list_when_no_reel_plan(self, tmp_path):
        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = None
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), [str(tmp_path / "song1.mp3")])

        result = handler._export_reel_videos(plan, {}, "OK")

        assert result == []
        coordinator.resolve_reel_plan.assert_called_once_with(plan, {})


class TestExportReelVideosSkipsExistingReels:
    """Skips tracks that already have a valid _REEL.mp4 file."""

    def test_skips_already_exported_reel(self, tmp_path):
        # Create a standard mp4 and an already-exported reel
        mp3 = tmp_path / "song1.mp3"
        mp3.write_bytes(b"x" * 100)
        standard_mp4 = tmp_path / "song1.mp4"
        standard_mp4.write_bytes(b"x" * 60_000)
        reel_mp4 = tmp_path / "song1_REEL.mp4"
        reel_mp4.write_bytes(b"x" * 60_000)  # > 50KB

        reel_plan = AutoVideoReelPlan(
            reel_template={"effect": "glow"},
            width=1080,
            height=1920,
            mp3s=[str(mp3)],
            bg_path="/tmp/bg.png",
            logo_path="/tmp/logo.png",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="balanced",
            export_workers=1,
        )

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), [str(mp3)])

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            result = handler._export_reel_videos(plan, {}, "OK")

        assert result == [str(reel_mp4)]
        # execute_single_export should NOT be called since reel already exists
        coordinator.execute_single_export.assert_not_called()


class TestExportReelVideosSuccessfulExport:
    """Happy path: reel is exported and renamed correctly."""

    def test_exports_and_renames_to_reel_suffix(self, tmp_path):
        mp3 = tmp_path / "track1.mp3"
        mp3.write_bytes(b"x" * 100)
        standard_mp4 = tmp_path / "track1.mp4"
        standard_mp4.write_bytes(b"x" * 60_000)  # Pre-existing standard

        reel_plan = AutoVideoReelPlan(
            reel_template={"effect": "zoom"},
            width=1080,
            height=1920,
            mp3s=[str(mp3)],
            bg_path="/tmp/bg.png",
            logo_path="",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="fast",
            export_workers=1,
        )

        def fake_execute_single_export(*, mp3_path, template, bg_path, logo_path, es):
            # Simulate the visualizer writing {stem}.mp4
            out = Path(es.output_dir) / f"{Path(mp3_path).stem}.mp4"
            out.write_bytes(b"REEL_VIDEO_DATA" * 5000)

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        coordinator.execute_single_export.side_effect = fake_execute_single_export
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), [str(mp3)])

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            result = handler._export_reel_videos(plan, {}, "OK")

        expected_reel = str(tmp_path / "track1_REEL.mp4")
        assert result == [expected_reel]
        # The reel file should exist
        assert Path(expected_reel).exists()
        # The standard MP4 should be restored
        assert standard_mp4.exists()

    def test_exports_multiple_tracks(self, tmp_path):
        mp3s = []
        for name in ["song1", "song2", "song3"]:
            mp3 = tmp_path / f"{name}.mp3"
            mp3.write_bytes(b"x" * 100)
            standard = tmp_path / f"{name}.mp4"
            standard.write_bytes(b"x" * 60_000)
            mp3s.append(str(mp3))

        reel_plan = AutoVideoReelPlan(
            reel_template={"effect": "zoom"},
            width=1080,
            height=1920,
            mp3s=mp3s,
            bg_path="/tmp/bg.png",
            logo_path="",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="balanced",
            export_workers=1,
        )

        def fake_execute(*, mp3_path, template, bg_path, logo_path, es):
            out = Path(es.output_dir) / f"{Path(mp3_path).stem}.mp4"
            out.write_bytes(b"REEL" * 2000)

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        coordinator.execute_single_export.side_effect = fake_execute
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), mp3s)

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            result = handler._export_reel_videos(plan, {}, "OK")

        assert len(result) == 3
        for name in ["song1", "song2", "song3"]:
            reel_path = tmp_path / f"{name}_REEL.mp4"
            assert reel_path.exists()
            # Standard MP4 should still exist
            assert (tmp_path / f"{name}.mp4").exists()


class TestExportReelVideosFailureHandling:
    """Individual track failures are logged and skipped."""

    def test_continues_after_individual_track_failure(self, tmp_path):
        mp3s = []
        for name in ["good1", "bad", "good2"]:
            mp3 = tmp_path / f"{name}.mp3"
            mp3.write_bytes(b"x" * 100)
            standard = tmp_path / f"{name}.mp4"
            standard.write_bytes(b"x" * 60_000)
            mp3s.append(str(mp3))

        reel_plan = AutoVideoReelPlan(
            reel_template={"effect": "zoom"},
            width=1080,
            height=1920,
            mp3s=mp3s,
            bg_path="/tmp/bg.png",
            logo_path="",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="balanced",
            export_workers=1,
        )

        call_count = {"n": 0}

        def fake_execute(*, mp3_path, template, bg_path, logo_path, es):
            call_count["n"] += 1
            stem = Path(mp3_path).stem
            if stem == "bad":
                raise RuntimeError("Export subprocess crashed")
            out = Path(es.output_dir) / f"{stem}.mp4"
            out.write_bytes(b"REEL" * 2000)

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        coordinator.execute_single_export.side_effect = fake_execute
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), mp3s)

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            result = handler._export_reel_videos(plan, {}, "OK")

        # Should have 2 successful reels (good1 and good2), skipping bad
        assert len(result) == 2
        assert str(tmp_path / "good1_REEL.mp4") in result
        assert str(tmp_path / "good2_REEL.mp4") in result
        # Standard MP4 for "bad" should still exist (restored from backup)
        assert (tmp_path / "bad.mp4").exists()
        # All 3 tracks attempted
        assert call_count["n"] == 3

    def test_emits_status_on_failure(self, tmp_path):
        mp3 = tmp_path / "failing.mp3"
        mp3.write_bytes(b"x" * 100)
        standard = tmp_path / "failing.mp4"
        standard.write_bytes(b"x" * 60_000)

        reel_plan = AutoVideoReelPlan(
            reel_template={},
            width=1080,
            height=1920,
            mp3s=[str(mp3)],
            bg_path="/tmp/bg.png",
            logo_path="",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="balanced",
            export_workers=1,
        )

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        coordinator.execute_single_export.side_effect = RuntimeError("boom")
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), [str(mp3)])

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            result = handler._export_reel_videos(plan, {}, "ALT")

        assert result == []
        # Should have emitted a failure status message
        calls = bus.music_event.emit.call_args_list
        failure_msgs = [
            c for c in calls
            if "failed" in str(c[0][0].get("message", ""))
        ]
        assert len(failure_msgs) >= 1
        assert "failing" in failure_msgs[0][0][0]["message"]
        assert "ALT" in failure_msgs[0][0][0]["message"]


class TestExportReelVideosUsesCorrectSettings:
    """Verifies the reel export passes correct resolution and template."""

    def test_passes_1080x1920_to_export(self, tmp_path):
        mp3 = tmp_path / "track.mp3"
        mp3.write_bytes(b"x" * 100)
        standard = tmp_path / "track.mp4"
        standard.write_bytes(b"x" * 60_000)

        reel_plan = AutoVideoReelPlan(
            reel_template={"reel": True},
            width=1080,
            height=1920,
            mp3s=[str(mp3)],
            bg_path="/tmp/reel_bg.png",
            logo_path="/tmp/reel_logo.png",
            output_dir=str(tmp_path),
            ffmpeg_path="/usr/bin/ffmpeg",
            speed_mode="very_fast",
            export_workers=1,
        )

        captured_es = {}

        def fake_execute(*, mp3_path, template, bg_path, logo_path, es):
            captured_es["width"] = es.width
            captured_es["height"] = es.height
            captured_es["speed_mode"] = es.speed_mode
            captured_es["template"] = template
            captured_es["bg_path"] = bg_path
            captured_es["logo_path"] = logo_path
            out = Path(es.output_dir) / f"{Path(mp3_path).stem}.mp4"
            out.write_bytes(b"REEL" * 2000)

        coordinator = MagicMock()
        coordinator.resolve_reel_plan.return_value = reel_plan
        coordinator.execute_single_export.side_effect = fake_execute
        bus = _FakeBus()
        handler = _FakeHandler(coordinator=coordinator, bus=bus)
        plan = _make_plan(str(tmp_path), [str(mp3)])

        with patch("python_app.app.auto_video_handlers.export_gate", _FakeExportGate()):
            handler._export_reel_videos(plan, {}, "OK")

        assert captured_es["width"] == 1080
        assert captured_es["height"] == 1920
        assert captured_es["speed_mode"] == "very_fast"
        assert captured_es["template"] == {"reel": True}
        assert captured_es["bg_path"] == "/tmp/reel_bg.png"
        assert captured_es["logo_path"] == "/tmp/reel_logo.png"
