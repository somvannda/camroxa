from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from platform_api.services.desktop_notification_admin_service import (
    NOTIFICATION_MESSAGE_EVENT,
    SOFTWARE_UPDATE_DOWNLOAD_URL_KEY,
    SOFTWARE_UPDATE_LIVE_HISTORY_KEY,
    SOFTWARE_UPDATE_LIVE_KEY,
    SOFTWARE_UPDATE_MANDATORY_KEY,
    SOFTWARE_UPDATE_PUBLISHED_AT_KEY,
    SOFTWARE_UPDATE_VERSION_KEY,
    InstallerCandidate,
    _summarize_release_notes_excerpt,
    apply_uploaded_installer_to_draft,
    get_published_desktop_release,
    get_software_update_config,
    move_installer_to_draft,
    publish_software_update,
    save_software_update_config,
    send_push_notification,
    sync_after_installer_delete,
    unpublish_software_update,
)


class _FakePool:
    def __init__(self, settings: dict[str, str] | None = None) -> None:
        self.settings = dict(settings or {})
        self.executed: list[tuple] = []
        self.blog_posts: list[dict] = []

    async def fetchrow(self, query: str, *args):
        q = " ".join(query.split()).lower()
        if "from blog_posts" in q:
            if "select 1" in q:
                slug = str(args[0]) if args else ""
                for post in self.blog_posts:
                    if post.get("slug") == slug:
                        return {"slug": slug}
                return None
            slug_base = str(args[1]) if len(args) > 1 else ""
            like_prefix = str(args[2]).rstrip("%") if len(args) > 2 else ""
            title = str(args[3]) if len(args) > 3 else ""
            for post in self.blog_posts:
                slug = str(post.get("slug") or "")
                if slug == slug_base or (like_prefix and slug.startswith(like_prefix)) or str(post.get("title") or "") == title:
                    return post
            return None
        key = str(args[0]) if args else ""
        value = self.settings.get(key)
        if value is None:
            return None
        return {"value": value}

    async def fetch(self, query: str):
        if "FROM users" in query:
            return [{"user_id": "user-1"}, {"user_id": "user-2"}]
        return []

    async def execute(self, query: str, *args):
        self.executed.append((query, args))
        q = " ".join(query.split()).lower()
        if "insert into system_settings" in q and len(args) >= 2:
            self.settings[str(args[0])] = str(args[1])
        if "insert into blog_posts" in q:
            self.blog_posts.append(
                {
                    "id": args[0],
                    "slug": args[1],
                    "title": args[2],
                    "is_published": True,
                }
            )
        if "update blog_posts" in q and "is_published = false" in q:
            for post in self.blog_posts:
                post["is_published"] = False
        if "update blog_posts" in q and "is_published = true" in q:
            post_id = args[0]
            for post in self.blog_posts:
                if post.get("id") == post_id:
                    post["is_published"] = True
                    post["title"] = args[1]
        return "UPDATE 1"


def _published_pool() -> _FakePool:
    return _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "1.2.6",
            SOFTWARE_UPDATE_DOWNLOAD_URL_KEY: "https://example.com/CamxoraSetup-1.2.6.exe",
            SOFTWARE_UPDATE_MANDATORY_KEY: "true",
            "desktop.software_update.release_notes": "1.2.6 notes",
            SOFTWARE_UPDATE_PUBLISHED_AT_KEY: "2026-08-13T00:00:00+00:00",
        }
    )


@pytest.mark.asyncio
async def test_get_software_update_config_reads_settings() -> None:
    pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "2.5.0",
            "desktop.software_update.download_url": "https://example.com/app.exe",
            "desktop.software_update.mandatory": "true",
            "desktop.software_update.release_notes": "Bug fixes",
        }
    )
    config = await get_software_update_config(pool)
    assert config.version == "2.5.0"
    assert config.download_url.endswith("app.exe")
    assert config.mandatory is True
    assert config.release_notes == "Bug fixes"


@pytest.mark.asyncio
async def test_save_software_update_config_persists_values() -> None:
    pool = _FakePool()
    config = await save_software_update_config(
        pool,
        version="3.0.0",
        download_url="https://example.com/v3",
        mandatory=False,
        release_notes="Initial release",
    )
    assert config.version == "3.0.0"
    assert pool.settings[SOFTWARE_UPDATE_VERSION_KEY] == "3.0.0"


@pytest.mark.asyncio
async def test_apply_uploaded_installer_to_draft_persists_download_url() -> None:
    pool = _FakePool()
    config = await apply_uploaded_installer_to_draft(
        pool,
        download_url="https://api.example.com/files/Camxora-2.5.0.zip",
        version="2.5.0",
    )
    assert config.download_url.endswith("Camxora-2.5.0.zip")
    assert config.version == "2.5.0"
    assert pool.settings[SOFTWARE_UPDATE_DOWNLOAD_URL_KEY].endswith("Camxora-2.5.0.zip")
    assert pool.settings[SOFTWARE_UPDATE_VERSION_KEY] == "2.5.0"


@pytest.mark.asyncio
async def test_get_published_desktop_release_requires_version_and_published_at() -> None:
    unpublished_pool = _FakePool({SOFTWARE_UPDATE_VERSION_KEY: "2.5.0"})
    assert await get_published_desktop_release(unpublished_pool) is None

    published_pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "2.5.0",
            SOFTWARE_UPDATE_PUBLISHED_AT_KEY: "2026-07-19T03:00:00+00:00",
        }
    )
    config = await get_published_desktop_release(published_pool)
    assert config is not None
    assert config.version == "2.5.0"
    assert config.published_at == "2026-07-19T03:00:00+00:00"


@pytest.mark.asyncio
async def test_publish_software_update_requires_version() -> None:
    pool = _FakePool()
    with pytest.raises(ValueError, match="version is required"):
        await publish_software_update(pool)


@pytest.mark.asyncio
async def test_publish_software_update_requires_download_url() -> None:
    pool = _FakePool({SOFTWARE_UPDATE_VERSION_KEY: "2.5.0"})
    with pytest.raises(ValueError, match="Download URL is required"):
        await publish_software_update(pool)


@pytest.mark.asyncio
async def test_publish_software_update_broadcasts_to_users() -> None:
    pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "2.5.0",
            SOFTWARE_UPDATE_DOWNLOAD_URL_KEY: "https://example.com/Camxora-2.5.0.zip",
        }
    )
    with patch(
        "platform_api.services.desktop_notification_admin_service.notify_software_update_available",
        new=AsyncMock(),
    ) as notify_mock:
        config, recipients, changelog_slug = await publish_software_update(pool)
    assert recipients == 2
    assert config.version == "2.5.0"
    assert config.published_at
    assert changelog_slug is None
    assert notify_mock.await_count == 2


@pytest.mark.asyncio
async def test_save_draft_does_not_replace_live_public_release() -> None:
    pool = _published_pool()
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.6"

    await save_software_update_config(
        pool,
        version="1.2.7",
        download_url="https://example.com/CamxoraSetup-1.2.7.exe",
        mandatory=True,
        release_notes="draft 1.2.7",
    )
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.6"
    assert public.mandatory is True
    draft = await get_software_update_config(pool)
    assert draft.version == "1.2.7"
    assert draft.published_at in {None, ""}
    assert draft.live_version == "1.2.6"


@pytest.mark.asyncio
async def test_upload_to_draft_does_not_replace_live_public_release() -> None:
    pool = _published_pool()
    await apply_uploaded_installer_to_draft(
        pool,
        download_url="https://example.com/CamxoraSetup-1.2.7.exe",
        version="1.2.7",
    )
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.6"
    draft = await get_software_update_config(pool)
    assert draft.version == "1.2.7"


@pytest.mark.asyncio
async def test_unpublish_restores_previous_live_and_hides_changelog() -> None:
    pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "1.2.6",
            SOFTWARE_UPDATE_DOWNLOAD_URL_KEY: "https://example.com/CamxoraSetup-1.2.6.exe",
            SOFTWARE_UPDATE_MANDATORY_KEY: "true",
            SOFTWARE_UPDATE_PUBLISHED_AT_KEY: "2026-08-13T00:00:00+00:00",
            SOFTWARE_UPDATE_LIVE_KEY: json.dumps(
                {
                    "version": "1.2.6",
                    "download_url": "https://example.com/CamxoraSetup-1.2.6.exe",
                    "mandatory": True,
                    "release_notes": "new",
                    "published_at": "2026-08-13T00:00:00+00:00",
                    "changelog_slug": "camxora-desktop-1.2.6",
                }
            ),
            SOFTWARE_UPDATE_LIVE_HISTORY_KEY: json.dumps(
                [
                    {
                        "version": "1.2.5",
                        "download_url": "https://example.com/CamxoraSetup-1.2.5.exe",
                        "mandatory": False,
                        "release_notes": "previous",
                        "published_at": "2026-08-11T00:00:00+00:00",
                        "changelog_slug": "camxora-desktop-1.2.5",
                    }
                ]
            ),
        }
    )
    pool.blog_posts.append(
        {
            "id": uuid4(),
            "slug": "camxora-desktop-1.2.6",
            "title": "Camxora Desktop 1.2.6",
            "is_published": True,
        }
    )
    result = await unpublish_software_update(pool)
    assert result.unpublished_version == "1.2.6"
    assert result.restored_live_version == "1.2.5"
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.5"
    assert public.mandatory is False
    assert pool.blog_posts[0]["is_published"] is False
    draft = await get_software_update_config(pool)
    assert draft.version == "1.2.6"
    assert draft.live_version == "1.2.5"


@pytest.mark.asyncio
async def test_unpublish_restores_previous_installer_when_history_missing() -> None:
    pool = _published_pool()
    candidates = [
        InstallerCandidate(
            version="1.2.6",
            download_url="https://example.com/CamxoraSetup-1.2.6.exe",
            filename="CamxoraSetup-1.2.6.exe",
        ),
        InstallerCandidate(
            version="1.2.5",
            download_url="https://example.com/CamxoraSetup-1.2.5.exe",
            filename="CamxoraSetup-1.2.5.exe",
        ),
    ]
    result = await unpublish_software_update(pool, installer_candidates=candidates)
    assert result.restored_live_version == "1.2.5"
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.5"
    assert public.mandatory is False


@pytest.mark.asyncio
async def test_move_live_installer_to_draft_restores_previous() -> None:
    pool = _published_pool()
    candidates = [
        InstallerCandidate(
            version="1.2.6",
            download_url="https://example.com/CamxoraSetup-1.2.6.exe",
            filename="CamxoraSetup-1.2.6.exe",
        ),
        InstallerCandidate(
            version="1.2.4",
            download_url="https://example.com/CamxoraSetup-1.2.4.exe",
            filename="CamxoraSetup-1.2.4.exe",
        ),
    ]
    result = await move_installer_to_draft(
        pool,
        version="1.2.6",
        download_url="https://example.com/CamxoraSetup-1.2.6.exe",
        filename="CamxoraSetup-1.2.6.exe",
        installer_candidates=candidates,
    )
    assert result.unpublished_version == "1.2.6"
    assert result.restored_live_version == "1.2.4"
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.4"


@pytest.mark.asyncio
async def test_delete_live_installer_restores_previous_and_clears_draft_url() -> None:
    pool = _published_pool()
    remaining = [
        InstallerCandidate(
            version="1.2.5",
            download_url="https://example.com/CamxoraSetup-1.2.5.exe",
            filename="CamxoraSetup-1.2.5.exe",
        )
    ]
    result = await sync_after_installer_delete(
        pool,
        filename="CamxoraSetup-1.2.6.exe",
        download_url="https://example.com/CamxoraSetup-1.2.6.exe",
        version="1.2.6",
        installer_candidates=remaining,
    )
    assert result.unpublished_version == "1.2.6"
    assert result.restored_live_version == "1.2.5"
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.5"
    draft = await get_software_update_config(pool)
    assert draft.download_url == ""


@pytest.mark.asyncio
async def test_save_live_draft_can_turn_off_force_update_in_place() -> None:
    pool = _published_pool()
    await save_software_update_config(
        pool,
        version="1.2.6",
        download_url="https://example.com/CamxoraSetup-1.2.6.exe",
        mandatory=False,
        release_notes="no longer forced",
    )
    public = await get_published_desktop_release(pool)
    assert public is not None
    assert public.version == "1.2.6"
    assert public.mandatory is False


@pytest.mark.asyncio
async def test_unpublish_software_update_clears_public_visibility() -> None:
    pool = _FakePool(
        {
            SOFTWARE_UPDATE_VERSION_KEY: "2.5.0",
            SOFTWARE_UPDATE_PUBLISHED_AT_KEY: "2026-07-19T00:00:00+00:00",
        }
    )
    result = await unpublish_software_update(pool)
    assert result.draft.published_at in {"", None}
    assert await get_published_desktop_release(pool) is None


@pytest.mark.asyncio
async def test_send_push_notification_broadcasts_message_event() -> None:
    pool = _FakePool()
    notification_service = AsyncMock()
    notification_service.push = AsyncMock()

    with patch(
        "platform_api.dependencies.get_notification_service",
        return_value=notification_service,
    ):
        history_item, recipients = await send_push_notification(
            pool,
            title="Maintenance",
            message="Desktop app will restart at midnight.",
        )

    assert recipients == 2
    assert history_item.title == "Maintenance"
    notification_service.push.assert_awaited()
    first_call = notification_service.push.await_args_list[0]
    assert first_call.args[1] == NOTIFICATION_MESSAGE_EVENT
    assert first_call.args[2]["title"] == "Maintenance"


def test_summarize_release_notes_excerpt_uses_added_bullets() -> None:
    notes = """## [0.2.3] - 2026-07-19

### Added

- Footer version badge (v0.2.3) next to the Sandbox API badge
- Start Export button on pending export rows

### Fixed

- Stale video export state no longer blocks Rebuild MP4
"""
    excerpt = _summarize_release_notes_excerpt(notes)
    assert excerpt.startswith("Footer version badge")
    assert "Start Export button" in excerpt
    assert "[0.2.3]" not in excerpt
    assert "### Added" not in excerpt
