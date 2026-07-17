"""Tests for usage transaction label helpers."""

from __future__ import annotations

from platform_api.services.usage_transaction_labels import (
    build_draft_usage_metadata,
    build_legacy_metadata_backfill,
    enrich_transaction_for_api,
    infer_purpose,
)


def test_infer_purpose_from_metadata_line_items() -> None:
    metadata = build_draft_usage_metadata(
        line_items=[
            {
                "operation": "title",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "amount_units": 32,
            },
            {
                "operation": "lyric",
                "provider": "slai",
                "model": "xiaomi/mimo-v2.5-pro",
                "amount_units": 216,
            },
        ],
        forced_title=False,
        forced_album=True,
    )
    purpose = infer_purpose("llm_draft", metadata)
    assert "Song draft" in purpose
    assert "Title generation" in purpose
    assert "Lyrics generation" in purpose


def test_enrich_transaction_signs_debit_amount() -> None:
    enriched = enrich_transaction_for_api(
        {
            "id": "tx-1",
            "user_id": "user-1",
            "amount": 248,
            "direction": "debit",
            "reason": "llm_draft",
            "metadata": {
                "operation": "song_draft",
                "provider": "slai",
                "model": "xiaomi/mimo-v2.5-pro",
                "purpose": "Song draft (Title + Lyrics)",
            },
        }
    )
    assert enriched["amount"] < 0
    assert enriched["purpose"] == "Song draft (Title + Lyrics)"
    assert enriched["provider"] == "slai"


def test_enrich_legacy_draft_shows_provider_and_model() -> None:
    enriched = enrich_transaction_for_api(
        {
            "id": "tx-2",
            "user_id": "user-1",
            "amount": 248,
            "direction": "debit",
            "reason": "llm_draft",
            "metadata": None,
        }
    )
    assert enriched["provider"] == "slai"
    assert enriched["model"] == "xiaomi/mimo-v2.5-pro"
    assert enriched["legacy"] is True
    assert len(enriched["line_items"]) == 2


def test_build_draft_usage_metadata_includes_batch_traceability() -> None:
    metadata = build_draft_usage_metadata(
        line_items=[
            {
                "operation": "lyric",
                "provider": "slai",
                "model": "xiaomi/mimo-v2.5-pro",
                "amount_units": 216,
            }
        ],
        forced_title=True,
        forced_album=True,
        extra={
            "source": "batch",
            "batch_id": "batch-1",
            "song_id": "song-9",
            "batch_index": 2,
        },
    )
    assert metadata["batch_id"] == "batch-1"
    assert metadata["song_id"] == "song-9"
    assert metadata["batch_index"] == 2


def test_enrich_transaction_exposes_attempts_used() -> None:
    enriched = enrich_transaction_for_api(
        {
            "id": "tx-3",
            "user_id": "user-1",
            "amount": 424,
            "direction": "debit",
            "reason": "llm_draft",
            "ref_id": "song-9",
            "metadata": {
                "operation": "song_draft",
                "provider": "slai",
                "model": "xiaomi/mimo-v2.5-pro",
                "batch_id": "batch-1",
                "song_id": "song-9",
                "attempts_used": 3,
            },
        }
    )
    assert enriched["song_id"] == "song-9"
    assert enriched["batch_id"] == "batch-1"
    assert enriched["attempts_used"] == 3
    assert enriched["ref_id"] == "song-9"


def test_enrich_transaction_exposes_llm_call_counts() -> None:
    enriched = enrich_transaction_for_api(
        {
            "id": "tx-4",
            "user_id": "user-1",
            "amount": 424,
            "direction": "debit",
            "reason": "llm_draft",
            "ref_id": "song-9",
            "metadata": {
                "operation": "song_draft",
                "provider": "slai",
                "model": "xiaomi/mimo-v2.5-pro",
                "attempts_used": 2,
                "llm_calls_title": 1,
                "llm_calls_album": 1,
                "llm_calls_lyric": 2,
            },
        }
    )
    assert enriched["llm_calls_title"] == 1
    assert enriched["llm_calls_album"] == 1
    assert enriched["llm_calls_lyric"] == 2


def test_build_legacy_metadata_backfill_for_shared_album_song() -> None:
    metadata = build_legacy_metadata_backfill(
        amount_units=248,
        reason="llm_draft",
        trace={"batch_id": "batch-1", "song_id": "song-2", "batch_index": 1},
    )
    assert metadata is not None
    assert "Song draft" in metadata["purpose"]
    assert "Title" in metadata["purpose"]
    assert "Lyrics" in metadata["purpose"]
    assert len(metadata["line_items"]) == 2
    assert metadata["batch_id"] == "batch-1"
    assert metadata["legacy_backfill"] is True
