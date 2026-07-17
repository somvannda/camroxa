"""Tests for streaming catalog visibility rules."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STREAMING_REPO = REPO_ROOT / "platform_api" / "repositories" / "streaming_repo.py"


def test_published_album_queries_require_at_least_one_published_track() -> None:
    source = STREAMING_REPO.read_text(encoding="utf-8")

    list_albums = _extract_function_sql(source, "list_published_albums")
    artist_albums = _extract_function_sql(source, "list_artist_albums")

    assert "HAVING COUNT(t.id) > 0" in list_albums
    assert "HAVING COUNT(t.id) > 0" in artist_albums


def test_genre_queries_present() -> None:
    source = STREAMING_REPO.read_text(encoding="utf-8")

    list_genres = _extract_function_sql(source, "list_genres")
    albums_by_genre = _extract_function_sql(source, "list_published_albums_by_genre")
    tracks_by_genre = _extract_function_sql(source, "list_published_tracks_by_genre")

    assert "GROUP BY genre" in list_genres
    assert "HAVING COUNT(t.id) > 0" in albums_by_genre
    assert "publish_status = 'published'" in tracks_by_genre


def _extract_function_sql(source: str, function_name: str) -> str:
    match = re.search(rf"async def {function_name}\(.*?\n\s+rows = await self\._pool\.fetch\(\s*\"\"\"(.*?)\"\"\"", source, re.S)
    assert match, f"Could not find SQL for {function_name}"
    return match.group(1)
