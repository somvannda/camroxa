"""Worker identity + job stage helpers."""

from __future__ import annotations

import pytest

from platform_api.services.job_types import stage_for_job_type
from platform_api.worker import (
    _job_timeout_seconds,
    _stale_running_seconds,
    _stale_sweep_interval_seconds,
    _worker_id,
)


@pytest.mark.parametrize(
    ("job_type", "stage"),
    [
        ("execute_batch", "draft"),
        ("draft", "draft"),
        ("suno_submit", "suno"),
        ("web_music_generate", "suno"),
        ("run_image_jobs", "images"),
        ("run_youtube_uploads", "images"),
        ("unknown_thing", "other"),
    ],
)
def test_stage_for_job_type(job_type: str, stage: str) -> None:
    assert stage_for_job_type(job_type) == stage


def test_worker_id_includes_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAMXORA_WORKER_NAME", "images@2")
    monkeypatch.setattr("platform_api.worker.socket.gethostname", lambda: "box")
    monkeypatch.setattr("platform_api.worker.os.getpid", lambda: 4242)
    assert _worker_id() == "box:images@2:4242"


def test_worker_id_falls_back_to_stage_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_WORKER_NAME", raising=False)
    monkeypatch.setenv("CAMXORA_WORKER_JOB_TYPES", "draft")
    monkeypatch.setattr("platform_api.worker.socket.gethostname", lambda: "box")
    monkeypatch.setattr("platform_api.worker.os.getpid", lambda: 7)
    assert _worker_id() == "box:draft:7"


def test_stale_sweep_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_WORKER_STALE_RUNNING_SECONDS", raising=False)
    monkeypatch.delenv("CAMXORA_WORKER_STALE_SWEEP_INTERVAL_SECONDS", raising=False)
    assert _stale_running_seconds() == 3600
    assert _stale_sweep_interval_seconds() == 300

    monkeypatch.setenv("CAMXORA_WORKER_STALE_RUNNING_SECONDS", "900")
    monkeypatch.setenv("CAMXORA_WORKER_STALE_SWEEP_INTERVAL_SECONDS", "60")
    assert _stale_running_seconds() == 900
    assert _stale_sweep_interval_seconds() == 60

    # Floors protect against disabling the sweep with a tiny value.
    monkeypatch.setenv("CAMXORA_WORKER_STALE_RUNNING_SECONDS", "5")
    monkeypatch.setenv("CAMXORA_WORKER_STALE_SWEEP_INTERVAL_SECONDS", "1")
    assert _stale_running_seconds() == 60
    assert _stale_sweep_interval_seconds() == 30

    monkeypatch.setenv("CAMXORA_WORKER_STALE_RUNNING_SECONDS", "not-an-int")
    assert _stale_running_seconds() == 3600


def test_job_timeout_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAMXORA_WORKER_JOB_TIMEOUT_SECONDS", raising=False)
    assert _job_timeout_seconds() == 0.0
    monkeypatch.setenv("CAMXORA_WORKER_JOB_TIMEOUT_SECONDS", "1800")
    assert _job_timeout_seconds() == 1800.0
    monkeypatch.setenv("CAMXORA_WORKER_JOB_TIMEOUT_SECONDS", "0")
    assert _job_timeout_seconds() == 0.0
