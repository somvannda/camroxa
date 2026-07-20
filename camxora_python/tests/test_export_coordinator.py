"""Unit tests for ExportCoordinator routing and cancel (REQ-2.5)."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from features.video.lib.render_scene_request import (
    ManualRenderSceneRequest,
    RenderSceneAssets,
    RenderSceneContext,
    RenderSceneOutput,
)
from features.video.services.export_coordinator import (
    CoordinatorExportRequest,
    ExportCoordinator,
    resolve_coordinator_backend,
)
from features.video.services.export_job import ExportSettings


def _scene(*, template: dict | None = None) -> ManualRenderSceneRequest:
    tpl = template or {"style": "orbit-spikes", "renderBaseHeight": 450.0}
    return ManualRenderSceneRequest(
        mode="manual",
        template=tpl,
        draft={},
        assets=RenderSceneAssets(
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
            audio_path="/b/track.mp3",
        ),
        output=RenderSceneOutput(resolution="1920x1080", width=1920, height=1080, fps=24),
        context=RenderSceneContext(
            template_id="tpl",
            branch=None,
            batch_id=None,
            role=None,
            draft_source="local",
        ),
    )


def _export_settings() -> ExportSettings:
    return ExportSettings(
        ffmpeg_path="ffmpeg",
        output_dir="/out",
        output_path="/out/track.mp4",
        fps=24,
        width=1920,
        height=1080,
        speed_mode="fast",
    )


def _warm_preview(template: dict | None = None) -> SimpleNamespace:
    tpl = template or {"style": "orbit-spikes", "renderBaseHeight": 450.0}
    return SimpleNamespace(
        _gl_ready=True,
        audio_path="/b/track.mp3",
        bg_path="/b/bg.jpg",
        logo_path="/b/logo.png",
        analysis_loading=False,
        analyzer=object(),
        template=tpl,
    )


def _request(*, preview: object | None = None, scene: ManualRenderSceneRequest | None = None) -> CoordinatorExportRequest:
    scene = scene or _scene()
    return CoordinatorExportRequest(
        mp3_path="/b/track.mp3",
        template=scene.template,
        background_path="/b/bg.jpg",
        logo_path="/b/logo.png",
        settings=_export_settings(),
        scene=scene,
        preview=preview,
        speed_mode="fast",
        acquire_gate=False,
    )


def test_resolve_backend_prefers_in_process_when_warm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")
    tpl = {"style": "orbit-spikes", "renderBaseHeight": 450.0}
    assert resolve_coordinator_backend(_request(preview=_warm_preview(tpl), scene=_scene(template=tpl))) == "in-process"


def test_resolve_backend_subprocess_without_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")
    assert resolve_coordinator_backend(_request(preview=None)) == "subprocess"


def test_resolve_backend_subprocess_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_INPROCESS_EXPORT", raising=False)
    assert resolve_coordinator_backend(_request(preview=_warm_preview())) == "subprocess"


def test_start_export_routes_in_process_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")
    calls: list[str] = []

    class _Session:
        def __init__(self, **kwargs: object) -> None:
            self._on_event = kwargs.get("on_event")

        def run(self) -> int:
            calls.append("in-process")
            if callable(self._on_event):
                self._on_event({"status": "running", "progress": 0.1})
            return 0

    class _Job:
        def __init__(self, **kwargs: object) -> None:
            calls.append("subprocess")

        def run_blocking(self) -> int:
            return 0

    monkeypatch.setattr(
        "features.video.services.export_coordinator.InProcessExportSession",
        _Session,
    )
    monkeypatch.setattr(
        "features.video.services.export_coordinator.ExportJob",
        _Job,
    )

    coordinator = ExportCoordinator()
    events: list[dict] = []
    coordinator.on_progress(events.append)
    coordinator.start_export(_request(preview=_warm_preview()))
    assert calls == ["in-process"]
    assert coordinator.last_exit_code == 0
    assert any(event.get("backend") == "in-process" for event in events)


def test_start_export_falls_back_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_INPROCESS_EXPORT", "1")

    class _Session:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run(self) -> int:
            return 2

    class _Job:
        backend_used = "daemon"

        def __init__(self, **kwargs: object) -> None:
            self.on_event = kwargs.get("on_event")

        def run_blocking(self) -> int:
            if callable(self.on_event):
                self.on_event({"status": "running", "message": "daemon job accepted", "progress": 0.5})
            return 0

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(
        "features.video.services.export_coordinator.InProcessExportSession",
        _Session,
    )
    monkeypatch.setattr(
        "features.video.services.export_coordinator.ExportJob",
        _Job,
    )

    coordinator = ExportCoordinator()
    events: list[dict] = []
    coordinator.on_progress(events.append)
    coordinator.start_export(_request(preview=_warm_preview()))
    assert coordinator.last_exit_code == 0
    assert any(event.get("status") == "warning" for event in events)
    assert any(event.get("fallbackFrom") == "in-process" for event in events)
    assert any(
        "retrying via subprocess" in str(event.get("message") or "").lower()
        for event in events
    )
    assert any(event.get("backendUsed") == "daemon" for event in events)


def test_start_export_logs_backend_on_completion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("CAMXORA_INPROCESS_EXPORT", raising=False)

    class _Job:
        backend_used = "subprocess"

        def __init__(self, **kwargs: object) -> None:
            pass

        def run_blocking(self) -> int:
            return 0

        def cancel(self) -> None:
            pass

    monkeypatch.setattr(
        "features.video.services.export_coordinator.ExportJob",
        _Job,
    )

    coordinator = ExportCoordinator()
    with caplog.at_level("INFO"):
        coordinator.start_export(_request(preview=None))
    assert coordinator.last_exit_code == 0
    assert any(
        "backendUsed=subprocess" in record.message and "fallbackFrom=-" in record.message
        for record in caplog.records
    )


def test_run_subprocess_export_reports_daemon_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Job:
        backend_used = "daemon"

        def __init__(self, **kwargs: object) -> None:
            self.on_event = kwargs.get("on_event")

        def run_blocking(self) -> int:
            if callable(self.on_event):
                self.on_event({"status": "running", "progress": 0.25})
            return 0

    monkeypatch.setattr(
        "features.video.services.export_coordinator.ExportJob",
        _Job,
    )
    from features.video.services.export_coordinator import (
        PipelineCoordinatorExportRequest,
        run_subprocess_export,
    )

    events: list[dict] = []
    code, backend_used, _job = run_subprocess_export(
        PipelineCoordinatorExportRequest(
            mp3_path="/b/track.mp3",
            template={"style": "orbit-spikes"},
            background_path="/b/bg.jpg",
            logo_path="/b/logo.png",
            settings=_export_settings(),
        ),
        on_event=events.append,
    )
    assert code == 0
    assert backend_used == "daemon"
    assert any(event.get("backendUsed") == "daemon" for event in events)


def test_cancel_export_stops_active_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_INPROCESS_EXPORT", raising=False)
    started = threading.Event()
    release = threading.Event()

    class _Job:
        def __init__(self, **kwargs: object) -> None:
            pass

        def run_blocking(self) -> int:
            started.set()
            release.wait(timeout=3.0)
            return 1

        def cancel(self) -> None:
            release.set()

    monkeypatch.setattr(
        "features.video.services.export_coordinator.ExportJob",
        _Job,
    )

    coordinator = ExportCoordinator()
    result: list[int] = []

    def _run() -> None:
        coordinator.start_export(_request(preview=None))
        result.append(coordinator.last_exit_code)

    thread = threading.Thread(target=_run)
    thread.start()
    assert started.wait(timeout=2.0)
    job_id = coordinator.running_job_id
    assert job_id
    coordinator.cancel_export(job_id)
    thread.join(timeout=3.0)
    assert not thread.is_alive()
    assert result == [1]
