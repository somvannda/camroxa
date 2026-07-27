"""Background DistroKid WAV fetch + Playwright upload worker."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from PySide6.QtCore import QThread, Signal

from features.distrokid.lib.album_scanner import scan_album_directory
from features.distrokid.lib.distrokid_readiness import find_matching_mp3_stem, wav_path_for_mp3
from features.distrokid.lib.distrokid_settings import DistroKidSettingsStore
from features.distrokid.lib.upload_history import sha256_file
from features.distrokid.services.upload_orchestrator import UploadOrchestrator
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError

_SAFE_NAME_RE = re.compile(r"[^\w\s\-'.()]+", re.UNICODE)


@dataclass(frozen=True)
class DistroKidUploadRequest:
    run_dir: str
    batch_id: str = ""
    album_name: str = ""
    role: str = "primary"
    auto_submit: bool | None = None
    job_id: str = ""
    artist_name: str = ""


def _sanitize_title(title: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("", str(title or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "track"


def _fallback_wav_target(*, output_dir: Path, title: str, track_no: int | None, role: str) -> Path:
    prefix = f"{max(1, int(track_no))}. " if isinstance(track_no, int) else ""
    suffix = "OK" if str(role).lower() == "primary" else "Alt"
    return output_dir / f"{prefix}{_sanitize_title(title)}_{suffix}.wav"


class DistroKidUploadWorker(QThread):
    """Ensure Suno WAVs exist for a run dir, then upload to DistroKid (soft failures)."""

    progressed = Signal(str)
    phase_changed = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, request: DistroKidUploadRequest, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._request = request
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            result = self._run_inner()
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc) or "DistroKid upload failed.")

    def _emit(self, message: str) -> None:
        self.progressed.emit(message)

    def _set_phase(self, phase: str, message: str = "") -> None:
        self.phase_changed.emit(phase)
        if message:
            self._emit(message)

    def _run_inner(self) -> dict:
        run_dir = Path(self._request.run_dir)
        if not run_dir.is_dir():
            raise RuntimeError(f"Run directory not found: {run_dir}")

        settings = DistroKidSettingsStore().load()
        album_name = (self._request.album_name or run_dir.name).strip()
        batch_id = str(self._request.batch_id or "").strip()
        artist_name = (self._request.artist_name or settings.artist_name or "").strip()
        auto_submit = (
            settings.auto_submit if self._request.auto_submit is None else bool(self._request.auto_submit)
        )

        if batch_id:
            self._set_phase("wav_downloading", "Resolving DistroKid WAV sources…")
            self._ensure_wavs(run_dir=run_dir, batch_id=batch_id, role_filter=self._request.role)

        album = scan_album_directory(
            run_dir,
            album_name=album_name,
            batch_id=batch_id,
            artist_name=artist_name,
        )
        if album is None:
            raise RuntimeError("No DistroKid tracks found in run directory.")
        if not album.is_ready_for_upload:
            missing = [t.title for t in album.tracks if not t.wav_exists]
            raise RuntimeError(f"Suno WAV files missing: {', '.join(missing[:6])}")

        tracks_payload = []
        for track in album.tracks:
            if not track.wav_path or not track.wav_path.exists():
                continue
            tracks_payload.append(
                {
                    "title": track.title,
                    "track_role": track.role,
                    "wav_byte_size": track.wav_byte_size,
                    "wav_sha256": sha256_file(track.wav_path),
                }
            )
        try:
            check = self._api.distrokid_history_check(album_name=album.name, tracks=tracks_payload)
            if check.get("duplicate"):
                matches = check.get("matches") or []
                raise RuntimeError(
                    f"Duplicate DistroKid upload blocked for album '{album.name}' "
                    f"({len(matches)} match(es))."
                )
        except PlatformApiError as exc:
            self._emit(f"DistroKid history check skipped: {exc}")

        self._set_phase("uploading", f"Uploading '{album.name}' to DistroKid…")
        orchestrator = UploadOrchestrator(settings)
        orchestrator.set_callbacks(on_log=self._emit)
        results = orchestrator.upload_albums(
            [album],
            auto_submit=auto_submit,
            stop_on_error=True,
        )
        ok = bool(results.get(album.name))
        if not ok:
            raise RuntimeError(album.error_message or f"DistroKid upload failed for '{album.name}'")

        meta = album.metadata or {}
        submitted = bool(meta.get("submitted", auto_submit))
        fingerprints = list(meta.get("track_fingerprints") or tracks_payload)

        if submitted:
            try:
                self._api.distrokid_history_record(
                    album_name=album.name,
                    directory_path=str(album.path),
                    batch_id=batch_id or None,
                    tracks=[
                        {
                            "title": str(item.get("title") or ""),
                            "track_role": str(item.get("role") or item.get("track_role") or ""),
                            "wav_byte_size": item.get("wav_byte_size"),
                            "wav_sha256": item.get("wav_sha256"),
                            "status": "success",
                        }
                        for item in fingerprints
                        if item.get("title")
                    ],
                )
            except PlatformApiError as exc:
                self._emit(f"DistroKid remote history record failed: {exc}")
            message = f"DistroKid upload submitted: {album.name}"
        else:
            message = f"DistroKid form ready (manual submit): {album.name}"

        return {
            "ok": True,
            "submitted": submitted,
            "album": album.name,
            "run_dir": str(run_dir),
            "job_id": self._request.job_id,
            "message": message,
        }

    def _ensure_wavs(self, *, run_dir: Path, batch_id: str, role_filter: str) -> None:
        sources = self._api.distrokid_wav_sources(batch_id)
        role_key = str(role_filter or "primary").lower()
        run_key = str(run_dir).strip().lower()

        # Prefer exact role match; then run-dir match; never silently mix both roles.
        wanted = [item for item in sources if str(item.get("role") or "").lower() == role_key]
        if not wanted:
            wanted = [
                item
                for item in sources
                if (
                    role_key == "primary"
                    and str(item.get("ok_run_dir") or "").strip().lower() == run_key
                )
                or (
                    role_key != "primary"
                    and str(item.get("alt_run_dir") or "").strip().lower() == run_key
                )
            ]
        if not wanted:
            raise RuntimeError(
                f"No DistroKid WAV sources for batch {batch_id} role={role_key}"
            )

        for item in wanted:
            if self._cancel:
                raise RuntimeError("DistroKid upload cancelled.")
            role = str(item.get("role") or role_key)
            title = str(item.get("title") or "track")
            track_no = item.get("track_number")
            track_no_int = int(track_no) if isinstance(track_no, int) else None
            mp3 = find_matching_mp3_stem(
                run_dir, title=title, track_no=track_no_int, role=role
            )
            target = wav_path_for_mp3(mp3) if mp3 is not None else _fallback_wav_target(
                output_dir=run_dir, title=title, track_no=track_no_int, role=role
            )
            if target.is_file() and target.stat().st_size > 1024:
                continue
            self._emit(f"Converting Suno WAV: {title} ({role})")
            job = self._api.distrokid_wav_convert(
                suno_task_id=str(item.get("suno_task_id") or ""),
                audio_id=str(item.get("audio_id") or "") or None,
                role=role,
                song_id=str(item.get("song_id") or "") or None,
                batch_id=batch_id,
            )
            job_id = str(job.get("id") or job.get("job_id") or "")
            if not job_id:
                raise RuntimeError(f"WAV convert did not return a job id for {title}")
            wav_url = self._poll_wav_url(job_id, title=title)
            self._download_wav(wav_url, target)
            self._emit(f"Downloaded WAV: {target.name}")

    def _poll_wav_url(self, job_id: str, *, title: str, attempts: int = 60, delay_s: float = 5.0) -> str:
        last_error = ""
        for _ in range(max(1, attempts)):
            if self._cancel:
                raise RuntimeError("DistroKid upload cancelled.")
            job = self._api.distrokid_wav_job(job_id)
            status = str(job.get("status") or "").lower()
            url = str(job.get("audio_wav_url") or job.get("audioWavUrl") or "").strip()
            if status in {"success", "completed", "done"} and url:
                return url
            if status in {
                "failed",
                "error",
                "create_task_failed",
                "generate_wav_failed",
                "callback_exception",
            }:
                raise RuntimeError(str(job.get("error_message") or f"WAV convert failed for {title}"))
            last_error = status or "pending"
            time.sleep(delay_s)
        raise RuntimeError(f"Timed out waiting for WAV ({title}): {last_error}")

    def _download_wav(self, url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        retries = 3
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        with tmp.open("wb") as handle:
                            for chunk in response.iter_bytes():
                                if self._cancel:
                                    raise RuntimeError("DistroKid upload cancelled.")
                                handle.write(chunk)
                tmp.replace(target)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._emit(f"WAV download retry {attempt}/{retries}: {exc}")
                time.sleep(min(8, attempt * 2))
        raise RuntimeError(f"Failed to download WAV to {target.name}: {last_exc}")
