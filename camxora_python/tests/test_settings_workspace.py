"""Settings workspace lib tests."""

from __future__ import annotations

from shared.lib.settings_workspace import (
    build_profile_draft,
    build_profile_payload,
    build_publication_draft,
    build_suno_settings_patch,
    build_system_settings_patch,
)
from shared.models.auth import ProfileResponse


def test_build_system_settings_patch_writes_export_workers_alias() -> None:
    current = {"perfExportWorkers": 1, "videoExportWorkers": 1}
    from shared.lib.settings_workspace import SystemSettingsDraft, build_system_settings_draft

    system = build_system_settings_draft(current)
    updated = SystemSettingsDraft(**{**system.__dict__, "perf_export_workers": 3})
    patch = build_system_settings_patch(updated, current)
    assert patch["perfExportWorkers"] == 3
    assert patch["videoExportWorkers"] == 3


def test_build_suno_settings_patch() -> None:
    current = {"sunoRetryCount": 3}
    from shared.lib.settings_workspace import build_suno_settings_draft, SunoSettingsDraft

    draft = build_suno_settings_draft(current)
    updated = SunoSettingsDraft(**{**draft.__dict__, "suno_retry_count": 5})
    patch = build_suno_settings_patch(updated, current)
    assert patch["sunoRetryCount"] == 5


def test_build_publication_draft_scheduled_publish_time() -> None:
    profile = ProfileResponse(
        id="p1",
        user_id="u1",
        name="Boss",
        youtube_config={"visibility": "scheduled", "publish_at": "14:35"},
    )
    draft = build_publication_draft(profile)
    assert draft.visibility == "scheduled"
    assert draft.publish_hour == "14"
    assert draft.publish_minute == "35"


def test_build_profile_payload_includes_image_mode() -> None:
    profile = ProfileResponse(
        id="p1",
        user_id="u1",
        name="Boss",
        image_config={"mode": "bg_only"},
    )
    draft = build_profile_draft(profile)
    payload = build_profile_payload(draft, profile)
    assert payload["image_config"]["mode"] == "bg_only"


def test_slugify_profile_folder_name() -> None:
    from shared.lib.settings_workspace import (
        resolve_profile_folder_name,
        slugify_profile_folder_name,
    )

    assert slugify_profile_folder_name("Beattok Remixes") == "beattok-remixes"
    assert slugify_profile_folder_name("Bass Drive") == "bass-drive"
    assert resolve_profile_folder_name("Beattok Remixes", "") == "beattok-remixes"
    assert resolve_profile_folder_name("Beattok Remixes", "custom-folder") == "custom-folder"


def test_build_profile_payload_defaults_folder_from_name() -> None:
    profile = ProfileResponse(id="p1", user_id="u1", name="Beattok Remixes")
    draft = build_profile_draft(profile)
    draft.folder_name = ""
    payload = build_profile_payload(draft, profile)
    assert payload["folder_name"] == "beattok-remixes"
