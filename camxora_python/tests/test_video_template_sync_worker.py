"""Tests for video template server sync worker."""

from __future__ import annotations

from features.video.workers.video_template_sync_worker import VideoTemplateSyncWorker
from shared.models.desktop import VideoWorkspaceState


class _FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def upsert_profile_video_template(self, profile_id, template_id, **kwargs):
        self.calls.append((profile_id, template_id, kwargs))
        return {"id": template_id}


def _run_worker(*, profiles: list, workspace: VideoWorkspaceState | None = None) -> tuple[_FakeApi, list[str]]:
    api = _FakeApi()
    messages: list[str] = []
    worker = VideoTemplateSyncWorker(
        api,  # type: ignore[arg-type]
        workspace=workspace
        or VideoWorkspaceState(
            templateId="tpl-1",
            template={"templateName": "Neon Drive"},
            templateName="Neon Drive",
        ),
        save_patch={"templateName": "Neon Drive"},
        profiles=profiles,
    )
    worker.succeeded.connect(messages.append)
    worker.failed.connect(messages.append)
    worker.run()
    return api, messages


def test_syncs_linked_profile_template():
    api, messages = _run_worker(
        profiles=[{"id": "prof-1", "video_template_id": "tpl-1", "reel_template_id": ""}],
    )
    assert len(api.calls) == 1
    assert api.calls[0][0] == "prof-1"
    assert api.calls[0][2]["set_as_profile_default"] is True
    assert "Synced template to 1 profile link" in messages[0]


def test_syncs_unlinked_template_to_first_profile():
    api, messages = _run_worker(
        profiles=[
            {"id": "prof-a", "video_template_id": "other", "reel_template_id": ""},
            {"id": "prof-b", "video_template_id": "", "reel_template_id": ""},
        ],
    )
    assert len(api.calls) == 1
    assert api.calls[0][0] == "prof-a"
    assert api.calls[0][2]["set_as_profile_default"] is False
    assert "Synced template to the server" in messages[0]


def test_no_profiles_keeps_local_only_message():
    api, messages = _run_worker(profiles=[])
    assert api.calls == []
    assert "Create a channel profile" in messages[0]
