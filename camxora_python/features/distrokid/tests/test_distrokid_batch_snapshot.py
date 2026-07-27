"""Tests for DistroKid batch snapshot + artist resolution helpers."""

from __future__ import annotations

from pathlib import Path

from features.distrokid.lib.distrokid_job_store import DistroKidJobStore
from shared.models.platform import BatchCreateRequest


def test_batch_create_request_includes_distrokid_snapshot() -> None:
    req = BatchCreateRequest(
        ok_profile_id="ok",
        alt_profile_id="alt",
        from_date="2026-07-27",
        to_date="2026-07-27",
        auto_distrokid=True,
        auto_reel_after_video=True,
    )
    payload = req.model_dump()
    assert payload["auto_distrokid"] is True
    assert payload["auto_reel_after_video"] is True


def test_job_store_persists_artist(tmp_path: Path) -> None:
    store = DistroKidJobStore(path=tmp_path / "jobs.json")
    job = store.upsert_pending(
        run_dir=str(tmp_path / "run"),
        batch_id="batch-1",
        role="primary",
        artist_name="Neon Channel",
    )
    reloaded = DistroKidJobStore(path=tmp_path / "jobs.json")
    found = reloaded.get(job.id)
    assert found is not None
    assert found.artist_name == "Neon Channel"
