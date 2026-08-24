"""Worker identity + job stage helpers."""

from __future__ import annotations

import pytest

from platform_api.services.job_types import stage_for_job_type
from platform_api.worker import _worker_id


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
