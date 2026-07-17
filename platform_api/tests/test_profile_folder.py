"""Profile folder helper tests."""

from __future__ import annotations

from platform_api.services.profile_folder import (
    resolve_profile_folder_name,
    slugify_profile_folder_name,
)


def test_slugify_profile_folder_name() -> None:
    assert slugify_profile_folder_name("Beattok Remixes") == "beattok-remixes"
    assert slugify_profile_folder_name("Bass Drive") == "bass-drive"


def test_resolve_profile_folder_name_prefers_explicit_value() -> None:
    assert resolve_profile_folder_name("Beattok Remixes", "custom-folder") == "custom-folder"
    assert resolve_profile_folder_name("Beattok Remixes", "") == "beattok-remixes"
