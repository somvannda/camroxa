"""Content pool service helpers."""

from __future__ import annotations

import pytest

from platform_api.services.content_pool_service import build_forced_opening_text, build_pool_inspiration_description


def test_build_pool_inspiration_description_appends_seeds() -> None:
    result = build_pool_inspiration_description(
        "EDM workout",
        title_seed="Midnight Run",
        album_seed="Night Drive",
    )
    assert "Inspiration (do not copy words): Midnight Run / Night Drive" in result
    assert result.startswith("EDM workout")


def test_build_forced_opening_text_joins_lines() -> None:
    assert build_forced_opening_text(line1="First line", line2="Second line") == "First line\nSecond line"
