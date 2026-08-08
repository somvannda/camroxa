"""Tests for genre-aware AI Structure diversity seeds."""

from __future__ import annotations

from platform_api.services.ai_structure_diversity import (
    DEFAULT_OVERUSED_STRUCTURE,
    build_ai_structure_diversity_system_rules,
    build_ai_structure_seed_user_block,
    choose_ai_structure_seed,
    classify_structure_bucket,
    families_for_bucket,
)


def test_classify_electronic_genres() -> None:
    assert classify_structure_bucket(["EDM", "Hands Up"]) == "electronic"
    assert classify_structure_bucket(["Progressive House"]) == "electronic"
    assert classify_structure_bucket(["Dance"]) == "electronic"
    assert classify_structure_bucket(["Electronic", "Club"]) == "electronic"
    # Dance Pop stays pop-leaning.
    assert classify_structure_bucket(["Dance Pop"]) == "pop"


def test_classify_pop_and_urban() -> None:
    assert classify_structure_bucket(["Dance Pop"]) == "pop"
    assert classify_structure_bucket(["Hip Hop", "Trap"]) == "urban"
    assert classify_structure_bucket(["R&B"]) == "urban"
    assert classify_structure_bucket([]) == "default"


def test_electronic_pool_includes_drop_families() -> None:
    ids = {family.id for family in families_for_bucket("electronic")}
    assert "build_drop" in ids
    assert "verse_build_drop" in ids
    assert "cold_drop" in ids
    assert "verse_drop_chorus_hybrid" in ids
    assert "festival_build_drop" in ids
    assert "eurodance_verse_chorus_drop" in ids
    assert "vocal_chop_drop" in ids
    assert len(families_for_bucket("electronic")) >= 20


def test_pop_pool_excludes_drop_families() -> None:
    ids = {family.id for family in families_for_bucket("pop")}
    assert "build_drop" not in ids
    assert "cold_drop" not in ids
    assert "cold_open_chorus" in ids
    assert "post_chorus_lift" in ids
    assert len(families_for_bucket("pop")) >= 10


def test_all_seed_count() -> None:
    from platform_api.services.ai_structure_diversity import STRUCTURE_FAMILIES

    assert len(STRUCTURE_FAMILIES) >= 26
    assert len({family.id for family in STRUCTURE_FAMILIES}) == len(STRUCTURE_FAMILIES)


def test_choose_seed_rotates_by_batch_index() -> None:
    first = choose_ai_structure_seed(genres=["Pop"], batch_index=0)
    second = choose_ai_structure_seed(genres=["Pop"], batch_index=1)
    assert first.id != second.id


def test_choose_seed_skips_avoided_fingerprints() -> None:
    first = choose_ai_structure_seed(genres=["Pop"], batch_index=0)
    second = choose_ai_structure_seed(
        genres=["Pop"],
        batch_index=0,
        avoid_fingerprints=[first.fingerprint],
    )
    assert second.fingerprint != first.fingerprint


def test_system_rules_ban_overused_layout() -> None:
    rules = build_ai_structure_diversity_system_rules()
    assert "Do NOT default" in rules
    assert "Pre-Chorus" in rules
    assert DEFAULT_OVERUSED_STRUCTURE in rules


def test_seed_user_block_includes_genres_and_avoids() -> None:
    block = build_ai_structure_seed_user_block(
        preferred_layout="[Chorus]\n[Verse]\n[Chorus]",
        avoid_structures=["[Verse] -> [Chorus] -> [Outro]"],
        genres=["Pop", "Dance Pop"],
    )
    assert "Pop" in block
    assert "Preferred section layout" in block
    assert "[Verse] -> [Chorus] -> [Outro]" in block


def test_ai_structure_user_prompt_includes_seed() -> None:
    from platform_api.services.generation_service import build_ai_structure_lyrics_user_prompt

    prompt = build_ai_structure_lyrics_user_prompt(
        mood="hopeful night drive",
        title="Neon Quiet",
        preferred_structure_layout="[Chorus]\n[Verse]\n[Chorus]",
        avoid_structures=["[Verse 1] -> [Pre-Chorus] -> [Chorus]"],
        description_genres=["Pop"],
    )
    assert "Preferred section layout" in prompt
    assert "[Chorus]" in prompt
    assert "Pop" in prompt
    assert "hopeful night drive" in prompt


def test_ai_structure_system_prompt_includes_diversity_rules() -> None:
    from platform_api.services.generation_service import build_ai_structure_lyrics_system_prompt

    prompt = build_ai_structure_lyrics_system_prompt(language="en")
    assert "Do NOT default" in prompt
    assert "Pre-Chorus and Final Chorus are optional" in prompt
