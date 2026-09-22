from __future__ import annotations

from uuid import UUID

from platform_api.services.web_music_service import _clip_is_playable
from platform_api.services.web_music_storage_keys import (
    usable_web_music_b2_key,
    web_music_object_key,
)

_TASK_ID = UUID("d46bc227-c204-4297-bc2c-2a8234026330")
_USER_ID = UUID("2b092c63-8a6d-465d-8fee-a90542e801a9")


def test_untitled_slug_key_is_not_usable() -> None:
    assert (
        usable_web_music_b2_key(
            f"web-music/{_USER_ID}/untitled-ok.mp3",
            _TASK_ID,
        )
        is None
    )


def test_task_nested_key_is_usable() -> None:
    key = web_music_object_key(_USER_ID, _TASK_ID, "ok", "mp3")
    assert key == f"web-music/{_USER_ID}/{_TASK_ID}/ok.mp3"
    assert usable_web_music_b2_key(key, _TASK_ID) == key


def test_clip_is_playable_rejects_shared_untitled_leftover() -> None:
    row = {
        "package_status_ok": "none",
        "packaged_storage_key_ok": None,
        "b2_storage_key_ok": f"web-music/{_USER_ID}/untitled-ok.mp3",
    }
    assert _clip_is_playable(row, variant="ok", task_id=_TASK_ID) is False


def test_clip_is_playable_accepts_packaged_ready() -> None:
    row = {
        "package_status_ok": "ready",
        "packaged_storage_key_ok": f"web-music/{_USER_ID}/{_TASK_ID}/ok.cxa1",
        "b2_storage_key_ok": f"web-music/{_USER_ID}/untitled-ok.mp3",
    }
    assert _clip_is_playable(row, variant="ok", task_id=_TASK_ID) is True
