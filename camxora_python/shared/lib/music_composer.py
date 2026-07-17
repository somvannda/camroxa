"""Music composer helpers — dates, history, profiles, draft seeds."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from shared.models.auth import ProfileResponse
from shared.models.platform import MusicHistoryBatch


@dataclass
class ComposerState:
    from_date: str
    to_date: str
    primary_profile_ids: list[str]
    secondary_profile_ids: list[str]
    description: str
    structure: str
    title: str
    album: str
    lyrics: str


@dataclass
class HistoryFiltersState:
    from_date: str = ""
    to_date: str = ""
    last_batch_only: bool = False


@dataclass
class DraftPoolSeedState:
    title_seed: str
    album_seed: str
    opening_seed: str | None


def blank_composer_state(today: str) -> ComposerState:
    return ComposerState(
        from_date=today,
        to_date=today,
        primary_profile_ids=[],
        secondary_profile_ids=[],
        description="",
        structure="",
        title="",
        album="",
        lyrics="",
    )


def get_inclusive_day_span(from_date: str, to_date: str) -> int | None:
    if not from_date or not to_date:
        return None
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError:
        return None
    if end < start:
        return None
    return (end - start).days + 1


def get_inclusive_date_list(from_date: str, to_date: str) -> list[str]:
    day_span = get_inclusive_day_span(from_date, to_date)
    if day_span is None:
        return []
    start = datetime.strptime(from_date, "%Y-%m-%d")
    return [(start + timedelta(days=index)).strftime("%Y-%m-%d") for index in range(day_span)]


def toggle_selected_profile_ids(current_ids: list[str], profile_id: str) -> list[str]:
    if not profile_id:
        return current_ids
    if profile_id in current_ids:
        return [item for item in current_ids if item != profile_id]
    return [*current_ids, profile_id]


def sanitize_selected_profile_ids(
    selected_ids: list[str],
    profiles: list[ProfileResponse],
    fallback_ids: list[str],
) -> list[str]:
    valid_ids = {profile.id for profile in profiles}
    deduped = [profile_id for index, profile_id in enumerate(selected_ids) if profile_id in valid_ids and profile_id not in selected_ids[:index]]
    if deduped:
        return deduped
    return [
        profile_id
        for index, profile_id in enumerate(fallback_ids)
        if profile_id and profile_id in valid_ids and profile_id not in fallback_ids[:index]
    ]


def extract_lyrics_opening(lyrics: str | None) -> str | None:
    if not lyrics:
        return None
    for line in lyrics.splitlines():
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("["):
            return trimmed
    return None


def build_history_avoid_lists(
    history_batches: list[MusicHistoryBatch],
    history_window: int,
) -> dict[str, list[str]]:
    titles: set[str] = set()
    albums: set[str] = set()
    openings: set[str] = set()
    batch_limit = max(1, (history_window + 9) // 10)

    for batch in history_batches[:batch_limit]:
        for song in batch.songs:
            title = (song.title or "").strip()
            album = (song.album or "").strip()
            opening = extract_lyrics_opening(song.lyrics)
            if title:
                titles.add(title)
            if album:
                albums.add(album)
            if opening:
                openings.add(opening)

    return {
        "titles": list(titles)[:200],
        "albums": list(albums)[:200],
        "openings": list(openings)[:200],
    }


def build_draft_description(base_description: str, pool_seeds: DraftPoolSeedState) -> str:
    inspiration = " / ".join(part for part in (pool_seeds.title_seed, pool_seeds.album_seed) if part)
    if not inspiration:
        return base_description
    return f"{base_description}\n\nInspiration (do not copy words): {inspiration}".strip()


def build_reservation_token() -> str:
    return str(uuid.uuid4())


def normalize_history_boundary(batch: MusicHistoryBatch, side: str) -> str:
    if side == "from":
        return batch.from_date or batch.created_at[:10]
    return batch.to_date or batch.updated_at[:10]


def matches_history_filters(batch: MusicHistoryBatch, filters: HistoryFiltersState, batch_index: int) -> bool:
    if filters.last_batch_only and batch_index > 0:
        return False
    batch_from = normalize_history_boundary(batch, "from")
    batch_to = normalize_history_boundary(batch, "to")
    if filters.from_date and batch_to < filters.from_date:
        return False
    if filters.to_date and batch_from > filters.to_date:
        return False
    return True


def effect_preview_from_creativity(creativity: int) -> dict[str, int]:
    value = max(0, min(100, creativity))
    return {
        "valence": max(5, min(95, round(20 + value * 0.7))),
        "danceability": max(5, min(95, round(15 + value * 0.75))),
        "instrumentalness": max(5, min(95, round(10 + value * 0.55))),
    }


def read_settings_dict(settings: Any) -> dict[str, Any]:
    if settings is None:
        return {}
    if isinstance(settings, dict):
        return settings
    if hasattr(settings, "model_dump"):
        return settings.model_dump(by_alias=True)
    return {}
