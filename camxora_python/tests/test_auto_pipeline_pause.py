"""Tests for Stop Exporting auto-pipeline pause."""

from __future__ import annotations

from shared.services import auto_pipeline_pause as pause


def setup_function() -> None:
    pause.resume_auto_pipeline()


def teardown_function() -> None:
    pause.resume_auto_pipeline()


def test_pause_blocks_until_resume() -> None:
    assert pause.is_auto_pipeline_paused() is False
    pause.pause_auto_pipeline("Stopped exporting by user")
    assert pause.is_auto_pipeline_paused() is True
    assert "Stopped" in pause.auto_pipeline_pause_reason()
    assert pause.resume_auto_pipeline() is True
    assert pause.is_auto_pipeline_paused() is False
    assert pause.resume_auto_pipeline() is False
