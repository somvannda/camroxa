"""Unit tests for AutoVideoCoordinator.resolve_reel_plan."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from python_app.features.auto_video.coordinator import (
    AutoVideoChannelPlan,
    AutoVideoCoordinator,
    AutoVideoReelPlan,
)


# ---------- Helpers ---------- #

@dataclass
class _FakeTemplateRow:
    template: dict


def _make_coordinator(
    *,
    profile: dict | None = None,
    template_row: Any = None,
) -> AutoVideoCoordinator:
    """Create a coordinator with minimal stubs for resolve_reel_plan testing."""
    logger = MagicMock()
    logger.warning = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()

    return AutoVideoCoordinator(
        db_cfg_accessor=lambda: {},
        settings_accessor=lambda: {},
        profile_accessor=lambda _pid: profile or {},
        get_video_template_fn=lambda _uid: template_row,
        resolved_output_resolution_fn=lambda _p: (1920, 1080),
        auto_video_batches_accessor=lambda: {},
        ffmpeg_path_accessor=lambda: "",
        export_batch_state_accessor=lambda: {},
        logger=logger,
    )


def _make_plan(**overrides) -> AutoVideoChannelPlan:
    defaults = dict(
        batch_id="batch-2024-01-15-1-5",
        profile_id="prof-123",
        role="OK",
        output_dir="/tmp/output",
        mp3s=["/tmp/output/song1.mp3", "/tmp/output/song2.mp3"],
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
    defaults.update(overrides)
    return AutoVideoChannelPlan(**defaults)


# ---------- Tests ---------- #

class TestResolveReelPlanSuccess:
    """Tests for successful reel plan resolution."""

    def test_returns_reel_plan_with_valid_template(self):
        tpl_row = _FakeTemplateRow(template={"effect": "glow"})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        plan = _make_plan()
        settings = {"videoExportSpeedMode": "fast", "videoExportWorkers": 3}

        result = coord.resolve_reel_plan(plan, settings)

        assert result is not None
        assert isinstance(result, AutoVideoReelPlan)

    def test_width_is_1080(self):
        tpl_row = _FakeTemplateRow(template={})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result.width == 1080

    def test_height_is_1920(self):
        tpl_row = _FakeTemplateRow(template={})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result.height == 1920

    def test_same_bg_path_as_standard_plan(self):
        tpl_row = _FakeTemplateRow(template={})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        plan = _make_plan(bg_path="/custom/bg.jpg")
        result = coord.resolve_reel_plan(plan, {})
        assert result.bg_path == "/custom/bg.jpg"

    def test_same_output_dir_as_standard_plan(self):
        tpl_row = _FakeTemplateRow(template={})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        plan = _make_plan(output_dir="/my/output")
        result = coord.resolve_reel_plan(plan, {})
        assert result.output_dir == "/my/output"

    def test_mp3s_copied_from_plan(self):
        tpl_row = _FakeTemplateRow(template={})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        plan = _make_plan(mp3s=["/a.mp3", "/b.mp3", "/c.mp3"])
        result = coord.resolve_reel_plan(plan, {})
        assert result.mp3s == ["/a.mp3", "/b.mp3", "/c.mp3"]

    def test_reel_template_extracted_from_row(self):
        tpl_row = _FakeTemplateRow(template={"effect": "zoom", "speed": 2})
        coord = _make_coordinator(
            profile={"reelTemplateId": "reel-tpl-1"},
            template_row=tpl_row,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result.reel_template == {"effect": "zoom", "speed": 2}


class TestResolveReelPlanMissingTemplate:
    """Tests for when reelTemplateId is empty or template is missing."""

    def test_returns_none_when_reel_template_id_empty(self):
        coord = _make_coordinator(
            profile={"reelTemplateId": ""},
            template_row=None,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result is None

    def test_returns_none_when_reel_template_id_missing(self):
        coord = _make_coordinator(
            profile={},
            template_row=None,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result is None

    def test_returns_none_when_template_row_not_found(self):
        coord = _make_coordinator(
            profile={"reelTemplateId": "nonexistent-id"},
            template_row=None,
        )
        result = coord.resolve_reel_plan(_make_plan(), {})
        assert result is None

    def test_emits_warning_when_reel_template_id_empty(self):
        coord = _make_coordinator(
            profile={"reelTemplateId": ""},
            template_row=None,
        )
        plan = _make_plan(role="OK")
        coord.resolve_reel_plan(plan, {})
        coord._logger.warning.assert_called_once()
        msg = coord._logger.warning.call_args[0][0]
        assert "Auto-Reel" in msg
        assert "OK" in msg

    def test_emits_warning_when_template_missing(self):
        coord = _make_coordinator(
            profile={"reelTemplateId": "missing-tpl"},
            template_row=None,
        )
        plan = _make_plan(role="ALT")
        coord.resolve_reel_plan(plan, {})
        coord._logger.warning.assert_called_once()
        msg = coord._logger.warning.call_args[0][0]
        assert "Auto-Reel" in msg
        assert "ALT" in msg
