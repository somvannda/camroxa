"""Quit-safety for auto-video orchestration workers."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.services import video_pipeline_activity as activity
from shared.services.video_pipeline_coordinator import VideoPipelineCoordinator
from shared.workers.data_workers import VideoPipelineOrchestrationPayload


def test_stop_disconnects_worker_so_late_payload_cannot_resume(qapp) -> None:
    activity.set_app_quitting(False)
    coordinator = VideoPipelineCoordinator(api=MagicMock())
    coordinator._active = True
    coordinator._api_outage = True

    started: list[object] = []
    coordinator._automation.start = MagicMock(side_effect=lambda *a, **k: started.append(1) or True)

    worker = MagicMock()
    worker.isRunning.return_value = False
    worker.succeeded = MagicMock()
    worker.failed = MagicMock()
    worker.finished = MagicMock()
    coordinator._worker = worker

    coordinator.stop()

    worker.succeeded.disconnect.assert_called()
    worker.failed.disconnect.assert_called()
    worker.finished.disconnect.assert_called()
    assert coordinator._worker is None

    # Queued delivery after stop must be a no-op (closeEvent processEvents race).
    payload = MagicMock(spec=VideoPipelineOrchestrationPayload)
    payload.workspace = MagicMock()
    coordinator._on_payload_ready(payload)
    assert started == []


def test_payload_ready_ignored_while_app_quitting(qapp) -> None:
    activity.set_app_quitting(True)
    try:
        coordinator = VideoPipelineCoordinator(api=MagicMock())
        coordinator._active = True
        started: list[object] = []
        coordinator._automation.start = MagicMock(side_effect=lambda *a, **k: started.append(1) or True)

        coordinator._on_payload_ready(MagicMock(spec=VideoPipelineOrchestrationPayload))
        assert started == []
    finally:
        activity.set_app_quitting(False)


def test_video_pipeline_skips_poll_without_session(qapp) -> None:
    activity.set_app_quitting(False)
    api = MagicMock()
    api.client._tokens_provider = lambda: None
    coordinator = VideoPipelineCoordinator(api=api)
    coordinator._active = True
    coordinator._poll()
    assert coordinator._worker is None


def test_automation_start_refuses_when_quitting() -> None:
    from features.video.services.pipeline_automation_service import PipelineAutomationService

    activity.set_app_quitting(True)
    try:
        service = PipelineAutomationService(api=MagicMock())
        candidate = MagicMock()
        assert service.start(candidate, settings={}) is False
    finally:
        activity.set_app_quitting(False)
