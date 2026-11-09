"""Desktop publishing models and auto-request builder tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from shared.models.publishing import CreatePublishJobRequest, PublishJob
from shared.workers.data_workers import PublishUploadWorker, _render_template


class FakeApi:
    def __init__(self, profile) -> None:
        self._profile = profile

    def list_profiles(self):
        return [self._profile]


def test_create_request_omits_none_fields() -> None:
    payload = CreatePublishJobRequest(
        profile_id="p1",
        title="Song",
        file_path="D:/runs/MERGED_OK.mp4",
    )
    dumped = payload.model_dump(exclude_none=True)
    assert dumped["profile_id"] == "p1"
    assert "batch_id" not in dumped
    assert dumped["platform"] == "youtube"


def test_publish_job_defaults() -> None:
    job = PublishJob(job_uid="job-1", status="processing")
    assert job.provider == "postforme"
    assert job.platform == "youtube"
    assert job.credits_charged == 0.0


def test_render_template_replaces_known_tokens() -> None:
    assert _render_template("{title} — Official", "Song One") == "Song One — Official"
    assert _render_template("{album}", "Album A") == "Album A"
    assert _render_template("", "Fallback") == "Fallback"


def test_auto_request_uses_profile_publication_defaults(tmp_path) -> None:
    video = tmp_path / "MERGED_OK.mp4"
    video.write_bytes(b"fake-mp4")
    profile = SimpleNamespace(
        id="profile-1",
        name="Boss Primary",
        youtube_config={
            "title_template": "{title} (Official Audio)",
            "description_template": "Listen to {title}",
            "tags": ["camxora", "music"],
            "visibility": "public",
            "category": "10",
            "made_for_kids": False,
            "ai_use": True,
        },
    )
    worker = PublishUploadWorker(
        FakeApi(profile),
        auto_context={
            "profile_id": "profile-1",
            "batch_id": "batch-1",
            "role": "ok",
            "run_dir": str(tmp_path),
            "merged_path": str(video),
        },
    )
    request = worker._build_auto_request()

    assert request.profile_id == "profile-1"
    assert request.title == f"{tmp_path.name} (Official Audio)"
    assert request.description == f"Listen to {tmp_path.name}"
    assert request.tags == ["camxora", "music"]
    assert request.privacy_status == "public"
    assert request.role == "OK"
    assert request.contains_synthetic_media is True
    assert request.file_size_bytes == video.stat().st_size


def test_auto_request_requires_profile_and_file() -> None:
    worker = PublishUploadWorker(FakeApi(None), auto_context={})
    with pytest.raises(RuntimeError):
        worker._build_auto_request()
