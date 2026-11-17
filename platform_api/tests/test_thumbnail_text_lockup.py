from __future__ import annotations

from platform_api.services.thumbnail_composite import (
    ThumbnailTextLockup,
    enrich_thumbnail_text_lockup,
)


def test_lockup_instruction_contains_only_three_lines_and_placement() -> None:
    prompt = enrich_thumbnail_text_lockup(
        "Clean art direction with no text.",
        ThumbnailTextLockup(
            title="BASS",
            subtitle="CAR MUSIC",
            subline="2026",
            placement="top_center",
            alignment="center",
        ),
    )

    assert 'Title: "BASS"' in prompt
    assert 'Subtitle: "CAR MUSIC"' in prompt
    assert 'Subline: "2026"' in prompt
    assert "top center" in prompt
    assert "No extra words" in prompt
    assert "Clean art direction with no text." in prompt


def test_lockup_without_subtitle_or_subline() -> None:
    prompt = enrich_thumbnail_text_lockup(
        "Art direction.",
        ThumbnailTextLockup(title="BASS", placement="bottom_center"),
    )

    assert 'Title: "BASS"' in prompt
    assert "Subtitle:" not in prompt
    assert "Subline:" not in prompt
    assert "bottom center" in prompt
