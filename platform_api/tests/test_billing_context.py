"""Tests for draft billing traceability context."""

from __future__ import annotations

from platform_api.models.billing_context import DraftBillingContext


def test_ref_id_prefers_song_id() -> None:
    ctx = DraftBillingContext(
        source="batch",
        batch_id="batch-1",
        song_id="song-42",
        batch_index=1,
    )
    assert ctx.ref_id == "song-42"


def test_ref_id_none_without_song_id() -> None:
    ctx = DraftBillingContext(source="api", batch_id="batch-1")
    assert ctx.ref_id is None


def test_to_metadata_omits_empty_fields() -> None:
    ctx = DraftBillingContext(source="api")
    assert ctx.to_metadata() == {"source": "api"}
