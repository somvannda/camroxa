"""Helpers for workspace pages that must reset when the logged-in account changes."""

from __future__ import annotations

from shared.models.auth import UserMeResponse
from shared.services.workspace_cache import WorkspaceCache


def cached_user_id(cache: WorkspaceCache | None) -> str | None:
    if cache is None or cache.me is None:
        return None
    return str(cache.me.id)


def account_cache_mismatch(loaded_user_id: str | None, cache: WorkspaceCache | None) -> bool:
    cached = cached_user_id(cache)
    if loaded_user_id is None or cached is None:
        return False
    return cached != loaded_user_id


def user_id_from_me(me: UserMeResponse | object | None) -> str | None:
    if me is None:
        return None
    user_id = getattr(me, "id", None)
    if user_id is None:
        return None
    return str(user_id)
