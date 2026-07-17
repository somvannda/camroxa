"""Profile folder-name helpers."""

from __future__ import annotations


def slugify_profile_folder_name(name: str) -> str:
    folder_name = str(name or "").strip().lower().replace(" ", "-").replace("/", "-")
    folder_name = "".join(character for character in folder_name if character.isalnum() or character == "-")
    while "--" in folder_name:
        folder_name = folder_name.replace("--", "-")
    folder_name = folder_name.strip("-")
    return (folder_name[:50] if folder_name else "profile")


def resolve_profile_folder_name(name: str, folder_name: str | None = None) -> str:
    cleaned = str(folder_name or "").strip()
    if cleaned:
        return cleaned[:50]
    return slugify_profile_folder_name(name)
