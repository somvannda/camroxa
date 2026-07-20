"""Tests for stale video pipeline state recovery."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from features.video.services.pipeline_automation_service import PipelineAutomationService
from shared.models.desktop import VideoExportState, VideoWorkspaceState
from shared.services.video_workspace_service import get_video_workspace_service


def _stale_workspace() -> VideoWorkspaceState:
    return VideoWorkspaceState(
        template_id="tpl",
        export=VideoExportState(
            running=True,
            merge_running=True,
            current_status="Exporting…",
            progress_percent=0,
        ),
    )


def test_recover_stale_state_clears_busy_and_export_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    workspace = _stale_workspace()
    get_video_workspace_service().set_workspace_state(workspace)

    service._busy = True
    published: list[VideoWorkspaceState] = []

    monkeypatch.setattr(service, "_publish_workspace", published.append)
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.any_video_pipeline_threads_running",
        lambda: False,
    )

    recovered = service.recover_stale_state()

    assert recovered is True
    assert service._busy is False
    assert len(published) == 1
    assert published[0].export.running is False
    assert published[0].export.merge_running is False
    assert "Recovered stale export state" in published[0].export.current_status


def test_recover_stale_state_noop_when_workers_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    get_video_workspace_service().set_workspace_state(_stale_workspace())
    service._busy = True
    published: list[VideoWorkspaceState] = []

    monkeypatch.setattr(service, "_publish_workspace", published.append)
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.any_video_pipeline_threads_running",
        lambda: True,
    )

    assert service.recover_stale_state() is False
    assert service._busy is True
    assert published == []


def test_is_busy_recovers_stale_state_before_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    get_video_workspace_service().set_workspace_state(_stale_workspace())
    service._busy = True

    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.any_video_pipeline_threads_running",
        lambda: False,
    )
    monkeypatch.setattr(service, "_publish_workspace", lambda _ws: None)

    assert service.is_busy() is False


def test_any_video_pipeline_threads_running_tracks_live_threads() -> None:
    from shared.services.video_pipeline_activity import (
        any_video_pipeline_threads_running,
        track_video_pipeline_thread,
    )

    live = MagicMock()
    live.isRunning.return_value = True
    live.finished = MagicMock()
    live.finished.connect = MagicMock()
    track_video_pipeline_thread(live)

    assert any_video_pipeline_threads_running() is True

    live.isRunning.return_value = False
    assert any_video_pipeline_threads_running() is False


def test_cancel_active_stops_live_export_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    worker = MagicMock()
    worker.isRunning.return_value = True
    worker.cancel = MagicMock()
    service._export_worker = worker
    service._busy = True

    statuses: list[str] = []
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.emit_shell_status",
        lambda msg, tone="neutral": statuses.append(str(msg)),
    )

    assert service.cancel_active() is True
    worker.cancel.assert_called_once()
    assert any("Stopping active" in s for s in statuses)


def test_cancel_active_clears_stale_busy_without_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = MagicMock()
    service = PipelineAutomationService(api)
    get_video_workspace_service().set_workspace_state(_stale_workspace())
    service._busy = True
    published: list[VideoWorkspaceState] = []

    monkeypatch.setattr(service, "_publish_workspace", published.append)
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.any_video_pipeline_threads_running",
        lambda: False,
    )
    monkeypatch.setattr(
        "features.video.services.pipeline_automation_service.emit_shell_status",
        lambda *_args, **_kwargs: None,
    )

    assert service.cancel_active() is True
    assert service._busy is False
    assert published
    assert published[-1].export.running is False
    assert published[-1].export.merge_running is False


def test_any_video_pipeline_threads_running_ignores_deleted_cpp_wrappers() -> None:
    from shared.services import video_pipeline_activity as activity

    zombie = MagicMock()
    zombie.isRunning.side_effect = RuntimeError(
        "libshiboken: Internal C++ object (VideoManualExportWorker) already deleted."
    )
    zombie.finished = MagicMock()
    zombie.finished.connect = MagicMock()
    activity.track_video_pipeline_thread(zombie)

    assert activity.any_video_pipeline_threads_running() is False
    assert zombie not in activity._alive


def test_shutdown_video_pipeline_threads_cancels_and_waits() -> None:
    from shared.services import video_pipeline_activity as activity

    live = MagicMock()
    live.isRunning.side_effect = [True, True, False]
    live.finished = MagicMock()
    live.finished.connect = MagicMock()
    live.cancel = MagicMock()
    live.wait = MagicMock(return_value=True)
    activity.track_video_pipeline_thread(live)

    activity.shutdown_video_pipeline_threads(wait_ms=100)

    live.cancel.assert_called_once()
    live.wait.assert_called()
