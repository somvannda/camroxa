"""Resolve DistroKid artist credits for Primary / Secondary / per-channel uploads."""

from __future__ import annotations

from typing import Literal

from features.distrokid.lib.distrokid_settings import DistroKidSettings

ArtistMode = Literal["single", "dual", "per_channel"]


def _normalize_role(role: str) -> str:
    key = str(role or "primary").strip().lower()
    if key in {"alt", "secondary"}:
        return "secondary"
    if key in {"ok", "primary"}:
        return "primary"
    return key or "primary"


def _context_primary(context: dict | None) -> str:
    if not isinstance(context, dict):
        return ""
    return str(context.get("primary_artist_name") or "").strip()


def _context_secondary(context: dict | None) -> str:
    if not isinstance(context, dict):
        return ""
    return str(context.get("secondary_artist_name") or "").strip()


def _context_profile_id(context: dict | None, role: str) -> str:
    if not isinstance(context, dict):
        return ""
    role_key = _normalize_role(role)
    if role_key == "secondary":
        return str(context.get("alt_profile_id") or context.get("secondary_profile_id") or "").strip()
    return str(context.get("ok_profile_id") or context.get("primary_profile_id") or "").strip()


def normalize_artist_mode(value: str | None) -> ArtistMode:
    key = str(value or "").strip().lower()
    if key == "single":
        return "single"
    if key == "dual":
        return "dual"
    return "per_channel"


def resolve_profile_id_for_role(
    *,
    role: str,
    profile_id: str = "",
    batch_context: dict | None = None,
) -> str:
    explicit = str(profile_id or "").strip()
    if explicit:
        return explicit
    return _context_profile_id(batch_context, role)


def resolve_distrokid_artist(
    *,
    role: str,
    settings: DistroKidSettings,
    batch_context: dict | None = None,
    profile_id: str = "",
) -> str:
    """Pick the DistroKid artist name for a run.

    - **per_channel**: use `channel_artists[profile_id]` (same DistroKid name can be
      assigned to multiple channels). Blank → channel profile name.
    - **single**: both Primary and Secondary WAV uploads use one artist.
    - **dual**: Primary channel → primary artist field; Secondary → secondary field.
    """
    mode = normalize_artist_mode(settings.artist_mode)
    legacy = str(settings.artist_name or "").strip()
    ctx_primary = _context_primary(batch_context)
    ctx_secondary = _context_secondary(batch_context)
    role_key = _normalize_role(role)
    resolved_profile_id = resolve_profile_id_for_role(
        role=role,
        profile_id=profile_id,
        batch_context=batch_context,
    )

    if mode == "per_channel":
        mapped = ""
        if resolved_profile_id:
            mapped = str((settings.channel_artists or {}).get(resolved_profile_id) or "").strip()
        role_fallback = ctx_secondary if role_key == "secondary" else ctx_primary
        for candidate in (mapped, role_fallback, legacy):
            if candidate:
                return candidate
        return ""

    if mode == "single":
        for candidate in (
            str(settings.single_artist_name or "").strip(),
            legacy,
            ctx_primary,
            ctx_secondary,
        ):
            if candidate:
                return candidate
        return ""

    if role_key == "secondary":
        for candidate in (
            str(settings.secondary_artist_name or "").strip(),
            ctx_secondary,
            legacy,
        ):
            if candidate:
                return candidate
        return ""

    for candidate in (
        str(settings.primary_artist_name or "").strip(),
        ctx_primary,
        legacy,
    ):
        if candidate:
            return candidate
    return ""
