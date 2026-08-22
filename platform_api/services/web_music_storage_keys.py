"""Backblaze object paths for Camxora Music leftovers and packages."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def normalize_clip_variant(variant: str | None) -> str:
    return "alt" if str(variant or "ok").strip().lower() == "alt" else "ok"


def web_music_object_key(user_id: UUID, task_id: UUID, variant: str, suffix: str) -> str:
    """Unique per generation. Never `web-music/{user}/untitled-ok.mp3` (shared collision)."""
    ext = str(suffix or "mp3").lstrip(".")
    return f"web-music/{user_id}/{task_id}/{normalize_clip_variant(variant)}.{ext}"


def b2_key_is_task_scoped(storage_key: str | None, task_id: UUID) -> bool:
    """True when the object path contains this task id (not a shared untitled-ok.mp3)."""
    parts = [part for part in str(storage_key or "").replace("\\", "/").split("/") if part]
    return str(task_id) in parts


def usable_web_music_b2_key(storage_key: Any, task_id: UUID) -> str | None:
    key = str(storage_key or "").strip()
    if key and b2_key_is_task_scoped(key, task_id):
        return key
    return None
