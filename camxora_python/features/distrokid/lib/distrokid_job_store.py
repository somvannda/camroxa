"""Local DistroKid job queue / status — soft stage persistence for Progress/Workflow."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

DistroKidJobStatus = Literal[
    "awaiting_short",
    "queued",
    "pending",
    "running",
    "wav_downloading",
    "uploading",
    "awaiting_manual_submit",
    "success",
    "failed",
    "skipped_duplicate",
    "skipped_no_entitlement",
    "cancelled",
]

_OPEN_STATUSES = frozenset(
    {
        "awaiting_short",
        "queued",
        "pending",
        "running",
        "wav_downloading",
        "uploading",
        "awaiting_manual_submit",
    }
)

_ACTIVE_PROGRESS_STATUSES = frozenset(
    {
        "awaiting_short",
        "queued",
        "pending",
        "running",
        "wav_downloading",
        "uploading",
        "awaiting_manual_submit",
        "success",
        "failed",
        "skipped_duplicate",
        "skipped_no_entitlement",
    }
)


def _default_store_path() -> Path:
    from shared.lib.app_paths import get_user_data_dir

    return get_user_data_dir() / "distrokid" / "jobs.json"


@dataclass
class DistroKidJob:
    id: str
    run_dir: str
    batch_id: str = ""
    role: str = "primary"
    profile_id: str = ""
    album_name: str = ""
    status: DistroKidJobStatus = "queued"
    wait_for_short: bool = False
    auto_submit: bool = False
    artist_name: str = ""
    message: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def dedupe_key(self) -> str:
        try:
            resolved = str(Path(self.run_dir).resolve()) if self.run_dir else ""
        except OSError:
            resolved = str(self.run_dir or "")
        return f"{self.batch_id}|{self.role}|{resolved}"


class DistroKidJobStore:
    """Machine-local DistroKid job list (survives soft failures for Workflow/UI)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_store_path()
        self._jobs: list[DistroKidJob] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._jobs = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._jobs = []
            return
        items = raw.get("jobs") if isinstance(raw, dict) else raw
        jobs: list[DistroKidJob] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    jobs.append(
                        DistroKidJob(
                            id=str(item.get("id") or uuid.uuid4()),
                            run_dir=str(item.get("run_dir") or ""),
                            batch_id=str(item.get("batch_id") or ""),
                            role=str(item.get("role") or "primary"),
                            profile_id=str(item.get("profile_id") or ""),
                            album_name=str(item.get("album_name") or ""),
                            status=str(item.get("status") or "queued"),  # type: ignore[arg-type]
                            wait_for_short=bool(item.get("wait_for_short", False)),
                            auto_submit=bool(item.get("auto_submit", False)),
                            artist_name=str(item.get("artist_name") or ""),
                            message=str(item.get("message") or ""),
                            created_at=float(item.get("created_at") or time.time()),
                            updated_at=float(item.get("updated_at") or time.time()),
                        )
                    )
                except Exception:
                    continue
        self._jobs = jobs

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "jobs": [asdict(job) for job in self._jobs[-200:]]}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_jobs(self) -> list[DistroKidJob]:
        return list(self._jobs)

    def get(self, job_id: str) -> DistroKidJob | None:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def find_open_by_dedupe(self, *, batch_id: str, role: str, run_dir: str) -> DistroKidJob | None:
        probe = DistroKidJob(id="x", run_dir=run_dir, batch_id=batch_id, role=role)
        key = probe.dedupe_key
        for job in reversed(self._jobs):
            if job.dedupe_key == key and job.status in _OPEN_STATUSES:
                return job
        return None

    def upsert_pending(
        self,
        *,
        run_dir: str,
        batch_id: str,
        role: str,
        album_name: str = "",
        wait_for_short: bool = False,
        auto_submit: bool = False,
        artist_name: str = "",
        profile_id: str = "",
    ) -> DistroKidJob:
        existing = self.find_open_by_dedupe(batch_id=batch_id, role=role, run_dir=run_dir)
        if existing is not None:
            existing.wait_for_short = wait_for_short
            existing.auto_submit = auto_submit
            if album_name:
                existing.album_name = album_name
            if artist_name:
                existing.artist_name = artist_name
            if profile_id:
                existing.profile_id = profile_id
            if existing.status not in {
                "running",
                "wav_downloading",
                "uploading",
                "awaiting_manual_submit",
            }:
                existing.status = "awaiting_short" if wait_for_short else "queued"
            existing.updated_at = time.time()
            self._save()
            return existing
        job = DistroKidJob(
            id=str(uuid.uuid4()),
            run_dir=run_dir,
            batch_id=batch_id,
            role=role or "primary",
            profile_id=profile_id,
            album_name=album_name,
            status="awaiting_short" if wait_for_short else "queued",
            wait_for_short=wait_for_short,
            auto_submit=auto_submit,
            artist_name=artist_name,
            message="Registered for DistroKid",
        )
        self._jobs.append(job)
        self._save()
        return job

    def update(
        self,
        job_id: str,
        *,
        status: DistroKidJobStatus | None = None,
        message: str | None = None,
    ) -> DistroKidJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        if status is not None:
            job.status = status
        if message is not None:
            job.message = message
        job.updated_at = time.time()
        self._save()
        return job

    def next_queued(self) -> DistroKidJob | None:
        for job in self._jobs:
            if job.status in {"queued", "pending"}:
                return job
        return None

    def awaiting_short_jobs(self) -> list[DistroKidJob]:
        return [job for job in self._jobs if job.status == "awaiting_short"]

    @staticmethod
    def _normalize_role(role: str) -> str:
        key = str(role or "primary").strip().lower()
        if key in {"alt", "secondary"}:
            return "secondary"
        if key in {"ok", "primary"}:
            return "primary"
        return key or "primary"

    @staticmethod
    def _resolved_run_dir(run_dir: str) -> str:
        text = str(run_dir or "").strip()
        if not text:
            return ""
        try:
            return str(Path(text).resolve())
        except OSError:
            return text

    def latest_for_run(
        self,
        *,
        batch_id: str = "",
        run_dir: str = "",
        role: str = "",
    ) -> DistroKidJob | None:
        """Prefer exact run_dir, then batch+role, then batch-only."""
        want_role = self._normalize_role(role) if role else ""
        want_dir = self._resolved_run_dir(run_dir)
        batch_key = str(batch_id or "").strip()

        if want_dir:
            for job in reversed(self._jobs):
                if self._resolved_run_dir(job.run_dir) == want_dir:
                    if want_role and self._normalize_role(job.role) != want_role:
                        continue
                    return job

        if batch_key and want_role:
            for job in reversed(self._jobs):
                if job.batch_id == batch_key and self._normalize_role(job.role) == want_role:
                    return job

        if batch_key:
            for job in reversed(self._jobs):
                if job.batch_id == batch_key:
                    return job
        return None

    def summary_for_workflow(
        self,
        *,
        batch_id: str = "",
        run_dir: str = "",
        role: str = "",
    ) -> dict[str, Any]:
        job = self.latest_for_run(batch_id=batch_id, run_dir=run_dir, role=role)
        if job is None:
            return {"status": "inactive", "percent": 0, "detail": "DistroKid not started"}
        mapping = {
            "awaiting_short": ("partial", 25, "Waiting for Short/Reel exports"),
            "queued": ("partial", 40, "Queued for DistroKid"),
            "pending": ("partial", 40, "Pending DistroKid"),
            "running": ("running", 70, job.message or "Uploading to DistroKid"),
            "wav_downloading": ("running", 55, job.message or "Downloading Suno WAV"),
            "uploading": ("running", 80, job.message or "Uploading to DistroKid"),
            "awaiting_manual_submit": ("partial", 90, "Form ready — submit manually on DistroKid"),
            "success": ("done", 100, job.message or "DistroKid upload submitted"),
            "failed": ("failed", 100, job.message or "DistroKid failed"),
            "skipped_duplicate": ("partial", 100, job.message or "Duplicate blocked"),
            "skipped_no_entitlement": ("inactive", 0, "DistroKid add-on inactive"),
            "cancelled": ("inactive", 0, "Cancelled"),
        }
        state, percent, detail = mapping.get(job.status, ("inactive", 0, job.status))
        return {
            "status": state,
            "percent": percent,
            "detail": detail,
            "job_status": job.status,
            "message": job.message,
            "album_name": job.album_name,
            "role": job.role,
        }

    def summary_for_progress(
        self,
        *,
        batch_id: str = "",
        run_dir: str = "",
        role: str = "",
    ) -> dict[str, Any]:
        """Compact Progress cell + detail payload (soft stage; never drives row Error)."""
        summary = self.summary_for_workflow(batch_id=batch_id, run_dir=run_dir, role=role)
        job_status = str(summary.get("job_status") or "")
        if not job_status:
            return {
                "compact": "—",
                "detail": "DistroKid not started",
                "job_status": "",
                "active": False,
            }
        compact_map = {
            "awaiting_short": "Awaiting Short",
            "queued": "Pending",
            "pending": "Pending",
            "running": "Running …",
            "wav_downloading": "WAV …",
            "uploading": "Uploading …",
            "awaiting_manual_submit": "Awaiting submit",
            "success": "Completed ✓",
            "failed": "Failed ✗",
            "skipped_duplicate": "Duplicate",
            "skipped_no_entitlement": "No add-on",
            "cancelled": "Cancelled",
        }
        return {
            "compact": compact_map.get(job_status, job_status),
            "detail": str(summary.get("detail") or ""),
            "message": str(summary.get("message") or ""),
            "job_status": job_status,
            "album_name": str(summary.get("album_name") or ""),
            "active": job_status in _ACTIVE_PROGRESS_STATUSES,
            "workflow_status": str(summary.get("status") or "inactive"),
            "percent": int(summary.get("percent") or 0),
        }
