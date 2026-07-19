"""Tests for music prompt genre validation and streaming genre resolution."""

from __future__ import annotations

import pytest

from platform_api.services.music_genre_utils import (
    normalize_description_genres,
    resolve_stream_genres,
)


def test_normalize_description_genres_trims_dedupes_and_limits() -> None:
    assert normalize_description_genres([" Eurodance ", "hands up", "EURODANCE"]) == [
        "Eurodance",
        "hands up",
    ]


def test_normalize_description_genres_rejects_long_values() -> None:
    with pytest.raises(ValueError, match="60"):
        normalize_description_genres(["x" * 61])


def test_normalize_description_genres_rejects_too_many() -> None:
    with pytest.raises(ValueError, match="10"):
        normalize_description_genres([f"Genre {index}" for index in range(11)])


def test_resolve_stream_genres_prefers_description_genres() -> None:
    primary, genres = resolve_stream_genres(
        description_genres=["Eurodance", "Hands Up"],
        suno_tags_text="pop, electronic",
    )
    assert primary == "Eurodance"
    assert genres == ["Eurodance", "Hands Up"]


def test_resolve_stream_genres_falls_back_to_suno_tags() -> None:
    primary, genres = resolve_stream_genres(
        description_genres=[],
        suno_tags_text="pop, electronic",
    )
    assert primary == "pop"
    assert genres == ["pop", "electronic"]


def test_resolve_stream_genres_ignores_suno_style_prompt() -> None:
    primary, genres = resolve_stream_genres(
        description_genres=[],
        suno_tags_text="",
    )
    assert primary is None
    assert genres == []
