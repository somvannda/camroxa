"""Tests for DistroKid job queue, Short gate, and history semantics."""

from __future__ import annotations

from pathlib import Path

from features.distrokid.lib.distrokid_job_store import DistroKidJobStore
from features.distrokid.lib.distrokid_readiness import short_exports_ready
from features.video.lib.render_scene_request import MIN_VALID_EXPORT_BYTES


def test_job_store_queues_and_promotes(tmp_path: Path) -> None:
    store = DistroKidJobStore(path=tmp_path / "jobs.json")
    job = store.upsert_pending(
        run_dir=str(tmp_path / "run"),
        batch_id="batch-1",
        role="primary",
        wait_for_short=True,
    )
    assert job.status == "awaiting_short"
    store.update(job.id, status="queued")
    assert store.next_queued() is not None
    # Second upsert for same role/dir reuses open job
    again = store.upsert_pending(
        run_dir=str(tmp_path / "run"),
        batch_id="batch-1",
        role="primary",
        wait_for_short=False,
    )
    assert again.id == job.id


def test_job_store_both_roles(tmp_path: Path) -> None:
    store = DistroKidJobStore(path=tmp_path / "jobs.json")
    primary = store.upsert_pending(run_dir=str(tmp_path / "ok"), batch_id="b", role="primary")
    secondary = store.upsert_pending(run_dir=str(tmp_path / "alt"), batch_id="b", role="secondary")
    assert primary.id != secondary.id
    assert len([j for j in store.list_jobs() if j.status == "queued"]) == 2


def test_short_exports_ready(tmp_path: Path) -> None:
    (tmp_path / "1. Song_OK.mp3").write_bytes(b"x")
    (tmp_path / "2. Song_OK.mp3").write_bytes(b"x")
    assert short_exports_ready(tmp_path) is False
    for name in ("1. Song_OK_REEL.mp4", "2. Song_OK_REEL.mp4"):
        (tmp_path / name).write_bytes(b"x" * (MIN_VALID_EXPORT_BYTES + 1))
    assert short_exports_ready(tmp_path) is True


def test_workflow_summary_states(tmp_path: Path) -> None:
    store = DistroKidJobStore(path=tmp_path / "jobs.json")
    job = store.upsert_pending(run_dir=str(tmp_path), batch_id="b", role="primary")
    store.update(job.id, status="awaiting_manual_submit", message="Review form")
    summary = store.summary_for_workflow(batch_id="b")
    assert summary["status"] == "partial"
    assert "manual" in summary["detail"].lower()


def test_progress_summary_and_role_isolation(tmp_path: Path) -> None:
    store = DistroKidJobStore(path=tmp_path / "jobs.json")
    primary = store.upsert_pending(run_dir=str(tmp_path / "ok"), batch_id="b", role="primary")
    secondary = store.upsert_pending(run_dir=str(tmp_path / "alt"), batch_id="b", role="secondary")
    store.update(primary.id, status="wav_downloading", message="Downloading WAV")
    store.update(secondary.id, status="skipped_duplicate", message="Duplicate blocked")

    primary_summary = store.summary_for_progress(batch_id="b", role="primary")
    secondary_summary = store.summary_for_progress(batch_id="b", role="secondary")
    assert primary_summary["compact"] == "WAV …"
    assert primary_summary["active"] is True
    assert secondary_summary["compact"] == "Duplicate"
    assert store.summary_for_workflow(batch_id="b", role="secondary")["status"] == "partial"
