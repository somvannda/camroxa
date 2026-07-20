"""MP3 on-disk naming helpers — mirrors platform_api batch_service Suno targets."""

from __future__ import annotations


def normalize_channel_role(role: str | None) -> str:
    normalized = str(role or "").strip().upper()
    if normalized in {"OK", "PRIMARY"}:
        return "OK"
    if normalized in {"ALT", "SECONDARY"}:
        return "ALT"
    return normalized or "OK"


def mp3_suffix_for_role(role: str | None) -> str:
    """Return the filename suffix used for channel MP3s on disk."""
    return "_OK.mp3" if normalize_channel_role(role) == "OK" else "_Alt.mp3"


def mp3_naming_hint(role: str | None) -> str:
    """Human-readable naming pattern for validation messages."""
    suffix = mp3_suffix_for_role(role)
    return f"{{track}}. {{title}}{suffix}"


def mp3_channel_label(role: str | None) -> str:
    normalized = normalize_channel_role(role)
    if normalized == "OK":
        return "Primary (OK)"
    if normalized == "ALT":
        return "Secondary (Alt)"
    return normalized
