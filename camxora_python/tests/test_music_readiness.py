from __future__ import annotations

from shared.lib.formatting import format_friendly_expiry
from shared.lib.music_readiness import evaluate_music_readiness
from shared.models.auth import ProfileResponse
from shared.models.platform import YouTubeConnectionResponse


def _profile(
    *,
    profile_id: str,
    name: str,
    video_template_id: str | None = None,
    youtube_config: dict | None = None,
) -> ProfileResponse:
    return ProfileResponse(
        id=profile_id,
        user_id="user-1",
        name=name,
        video_template_id=video_template_id,
        youtube_config=youtube_config,
    )


def test_format_friendly_expiry_from_iso_string() -> None:
    text = format_friendly_expiry("2026-08-12T09:30:20.199251Z")
    assert text.startswith("Aug 12, 2026")


def test_evaluate_music_readiness_blocks_generate_until_preferences_ready(tmp_path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_text("bin", encoding="utf-8")
    downloads = tmp_path / "downloads"
    suno = tmp_path / "suno"
    merged = tmp_path / "merged"
    bg = tmp_path / "bg"
    th = tmp_path / "th"
    for folder in (downloads, suno, merged, bg, th):
        folder.mkdir()
    (bg / "one.png").write_bytes(b"png")
    (th / "two.png").write_bytes(b"png")

    profiles = [
        _profile(profile_id="p1", name="Primary", video_template_id="tpl-1"),
        _profile(profile_id="p2", name="Secondary", video_template_id="tpl-2"),
    ]
    connections = [
        YouTubeConnectionResponse(profile_id="p1", profile_name="Primary", status="connected"),
        YouTubeConnectionResponse(profile_id="p2", profile_name="Secondary", status="connected"),
    ]
    settings = {
        "ffmpegPath": str(ffmpeg),
        "downloadsDir": str(downloads),
        "sunoOutputDir": str(suno),
        "mergedDir": str(merged),
        "imageBackgroundSamplesDir": str(bg),
        "imageThumbnailSamplesDir": str(th),
        "styleStrength": 80,
    }
    for profile in profiles:
        profile.youtube_config = {
            "visibility": "unlisted",
            "made_for_kids": False,
            "ai_use": True,
            "category": "10",
            "title_template": "{title}",
            "description_template": "{description}",
        }

    report = evaluate_music_readiness(
        selected_profiles=profiles,
        settings=settings,
        youtube_connections=connections,
        bg_sample_count=1,
        th_sample_count=1,
    )
    assert report.generate_ready
    assert report.upload_ready


def test_evaluate_music_readiness_upload_requires_publication() -> None:
    profile = _profile(profile_id="p1", name="Primary", video_template_id="tpl-1")
    connections = [YouTubeConnectionResponse(profile_id="p1", profile_name="Primary", status="connected")]
    report = evaluate_music_readiness(
        selected_profiles=[profile],
        settings={},
        youtube_connections=connections,
    )
    upload_items = [item for item in report.items if item.required_for_upload]
    assert upload_items
    assert not report.upload_ready


def test_missing_setup_items_still_notify(tmp_path, monkeypatch) -> None:
    """Bell notifications must surface incomplete generate prerequisites."""
    from shared.models.notification_item import notification_item_from_setup

    monkeypatch.setattr(
        "shared.lib.music_readiness.SERVER_MANAGED_SAMPLE_PACKS",
        False,
    )
    profile = _profile(profile_id="p1", name="Primary", video_template_id=None)
    report = evaluate_music_readiness(
        selected_profiles=[profile],
        settings={},
        youtube_connections=[],
        bg_sample_count=0,
        th_sample_count=0,
    )
    incomplete = [item for item in report.items if not item.complete and item.required_for_generate]
    assert any(item.id == "profile:p1:video_template" for item in incomplete)
    assert any(item.id == "pref:bg_installed" for item in incomplete)
    assert any(item.id == "pref:th_installed" for item in incomplete)
    assert not any(item.id == "pref:style_strength" for item in report.items)

    notifications = [notification_item_from_setup(item) for item in incomplete]
    assert notifications
    assert all(item.kind == "setup" for item in notifications)
    assert any("sample pack" in item.title.lower() for item in notifications)


def test_server_managed_sample_packs_skip_local_install_checks() -> None:
    profile = _profile(profile_id="p1", name="Primary", video_template_id="tpl-1")
    report = evaluate_music_readiness(
        selected_profiles=[profile],
        settings={},
        youtube_connections=[],
        bg_sample_count=0,
        th_sample_count=0,
    )
    item_ids = {item.id for item in report.items}
    assert "pref:bg_dir" not in item_ids
    assert "pref:th_dir" not in item_ids
    assert "pref:bg_installed" not in item_ids
    assert "pref:th_installed" not in item_ids
