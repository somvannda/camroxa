"""Tests for model cost seed operation scoping."""

from __future__ import annotations

from platform_api.ai.types import IMAGE_OPERATIONS, TEXT_OPERATIONS
from platform_api.services.model_cost_estimates import (
    build_seed_cost_rows,
    estimate_cost_usd,
    operation_types_for_model,
)


def test_slai_mimo_is_text_only() -> None:
    ops = operation_types_for_model("slai", "xiaomi/mimo-v2.5-pro")
    assert "lyric" in ops
    assert "music" not in ops
    assert "channel_logo" not in ops


def test_slai_gpt_image_is_image_only() -> None:
    ops = operation_types_for_model("slai", "cx/gpt-image-2.5")
    assert "channel_logo" in ops
    assert "music" not in ops
    assert "lyric" not in ops


def test_slai_gpt56_models_are_text_only() -> None:
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        ops = operation_types_for_model("slai", model)
        assert "lyric" in ops
        assert "music" not in ops
        assert "channel_logo" not in ops


def test_seed_rows_exclude_slai_music() -> None:
    rows = build_seed_cost_rows()
    slai_music = [
        row
        for row in rows
        if row["ai_service"] == "slai" and row["operation_type"] == "music"
    ]
    assert slai_music == []


def test_mimo_album_cost_matches_slai_shop_calibration() -> None:
    cost = estimate_cost_usd(
        ai_service="slai",
        sub_model="xiaomi/mimo-v2.5-pro",
        operation_type="album",
    )
    assert cost is not None
    assert 0.00001 < cost < 0.00003


def test_mimo_lyric_cost_matches_slai_shop_calibration() -> None:
    cost = estimate_cost_usd(
        ai_service="slai",
        sub_model="xiaomi/mimo-v2.5-pro",
        operation_type="lyric",
    )
    assert cost is not None
    # ~1200 tokens * $0.0001414/1K
    assert 0.00014 < cost < 0.00020


def test_slai_models_seed_with_usd_estimates() -> None:
    rows = build_seed_cost_rows()
    mimo = [r for r in rows if r["sub_model"] == "xiaomi/mimo-v2.5-pro"]
    gpt56 = [r for r in rows if r["sub_model"] in {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}]
    image = [r for r in rows if r["sub_model"] == "cx/gpt-image-2.5"]
    assert len(mimo) == len(TEXT_OPERATIONS)
    assert len(gpt56) == 3 * len(TEXT_OPERATIONS)
    assert len(image) == len(IMAGE_OPERATIONS)
    assert all(r["cost_usd"] > 0 for r in mimo + gpt56 + image)


def test_cgpt_web_not_in_registry_seed() -> None:
    rows = build_seed_cost_rows()
    cgpt = [row for row in rows if "cgpt-web" in row.get("sub_model", "")]
    assert cgpt == []


def test_suno_music_models_seed_with_music_operations() -> None:
    rows = build_seed_cost_rows()
    v5 = [row for row in rows if row["ai_service"] == "suno" and row["sub_model"] == "V5"]
    v55 = [row for row in rows if row["ai_service"] == "suno" and row["sub_model"] == "V5_5"]
    assert {row["operation_type"] for row in v5} == {"music"}
    assert {row["operation_type"] for row in v55} == {"music"}
    assert all(row["cost_usd"] == 0.06 for row in v5 + v55)
    assert all(
        "Suno pack: 12 credits" in (row["notes"] or "") for row in v5 + v55
    )


def test_suno_lyrics_model_only_seeds_lyric_operation() -> None:
    ops = operation_types_for_model("suno", "lyrics")
    assert ops == ["lyric"]
    rows = build_seed_cost_rows()
    lyric_rows = [
        row
        for row in rows
        if row["ai_service"] == "suno" and row["sub_model"] == "lyrics"
    ]
    assert len(lyric_rows) == 1
    assert lyric_rows[0]["operation_type"] == "lyric"
    assert lyric_rows[0]["cost_usd"] == 0.004
