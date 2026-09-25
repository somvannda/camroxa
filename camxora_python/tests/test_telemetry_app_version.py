"""Telemetry/log payloads must report the real app version, not a hardcoded string.

Ops relies on `app_version` / `appVersion` to verify which desktop build a user
runs (e.g. confirming a forced update landed). These payloads previously sent the
literal "camxora_python", which made rollout verification impossible.
"""

from __future__ import annotations


class _StubLogger:
    def __init__(self, text: str = "line one\nline two") -> None:
        self._text = text

    def snapshot_text(self, **_kwargs: object) -> str:
        return self._text


def test_build_client_log_payload_reports_app_version(monkeypatch) -> None:
    from shared.services import log_sync

    monkeypatch.setattr(log_sync, "get_app_logger", lambda: _StubLogger())
    monkeypatch.setattr(log_sync, "get_app_version", lambda: "9.9.9")

    payload = log_sync.build_client_log_payload()

    assert payload is not None
    assert payload["appVersion"] == "9.9.9"


def test_build_client_log_payload_empty_returns_none(monkeypatch) -> None:
    from shared.services import log_sync

    monkeypatch.setattr(log_sync, "get_app_logger", lambda: _StubLogger("   "))
    assert log_sync.build_client_log_payload() is None


def test_pipeline_telemetry_reports_app_version(monkeypatch) -> None:
    from features.video.lib import export_telemetry
    from features.video.services import pipeline_automation_service as mod

    captured: dict[str, object] = {}
    monkeypatch.setattr(export_telemetry, "collect_hardware_hints", lambda codec=None: {})
    monkeypatch.setattr(
        export_telemetry,
        "report_video_telemetry_async",
        lambda api, payload: captured.update(payload),
    )
    monkeypatch.setattr(mod, "get_app_version", lambda: "9.9.9")

    class _Dummy:
        _active_run_key = "run-1"
        _api = object()

    mod.PipelineAutomationService._report_pipeline_telemetry(
        _Dummy(),
        operation_type="auto_video",
        track_count=2,
        completed_count=1,
        codec="libx264",
    )

    assert captured["app_version"] == "9.9.9"
