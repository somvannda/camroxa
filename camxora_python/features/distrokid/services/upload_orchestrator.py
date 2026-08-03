"""DistroKid upload orchestrator — WAV-only, no Mixea / local convert."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from features.distrokid.lib.distrokid_settings import DistroKidSettings, DistroKidSettingsStore
from features.distrokid.lib.upload_history import UploadHistory, sha256_file
from features.distrokid.models.distrokid_models import Album, AlbumStatus, TrackStatus
from features.distrokid.services.browser import BrowserAutomation
from features.distrokid.services.distrokid import DistroKidAutomation, DistroKidError
from features.distrokid.services.element_resolver import ElementResolver
from features.distrokid.services.form_automator import FormAutomator

logger = logging.getLogger(__name__)


class UploadOrchestrator:
    """Upload CAMXORA albums to DistroKid using Playwright FormAutomator."""

    def __init__(
        self,
        settings: DistroKidSettings | None = None,
        *,
        history: UploadHistory | None = None,
        duplicate_checker: Callable[[Album], str | None] | None = None,
    ) -> None:
        self.settings = settings or DistroKidSettingsStore().load()
        self.upload_history = history or UploadHistory()
        self.duplicate_checker = duplicate_checker
        self.browser: BrowserAutomation | None = None
        self.distrokid: DistroKidAutomation | None = None
        self._is_processing = False
        self._should_stop = False
        self._on_log: Optional[Callable[[str], None]] = None
        self._on_progress: Optional[Callable[[str, int, int, str], None]] = None
        self._on_album_complete: Optional[Callable[[Album, bool], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_awaiting_login: Optional[Callable[[], None]] = None

    def set_callbacks(
        self,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[str, int, int, str], None]] = None,
        on_album_complete: Optional[Callable[[Album, bool], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_awaiting_login: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_log = on_log
        self._on_progress = on_progress
        self._on_album_complete = on_album_complete
        self._on_error = on_error
        self._on_awaiting_login = on_awaiting_login

    def stop(self) -> None:
        self._should_stop = True

    def _log(self, message: str, level: str = "info") -> None:
        getattr(logger, level, logger.info)(message)
        if self._on_log:
            self._on_log(message)

    def _update_progress(self, album_name: str, current: int, total: int, message: str) -> None:
        if self._on_progress:
            self._on_progress(album_name, current, total, message)

    def connect_session(self, *, headless: bool = False) -> bool:
        """Launch browser and ensure DistroKid login (manual Google Sign-In if needed)."""
        self.browser = BrowserAutomation(headless=headless)
        self.browser.launch()
        self.distrokid = DistroKidAutomation(self.browser)
        self.distrokid.set_callbacks(on_log=self._on_log)
        if self._on_awaiting_login:
            self._on_awaiting_login()
        return bool(self.distrokid.login())

    def close(self) -> None:
        if self.browser is not None:
            try:
                self.browser.close()
            except Exception as exc:  # noqa: BLE001
                self._log(f"Error closing browser: {exc}", "warning")
        self.browser = None
        self.distrokid = None

    def _validate_album_for_upload(self, album: Album) -> str | None:
        if not album.tracks:
            return f"Album '{album.name}' has no tracks"
        missing_wav = [t.title for t in album.tracks if not t.wav_exists]
        if missing_wav:
            return f"Album '{album.name}' missing Suno WAV files: {', '.join(missing_wav[:5])}"
        if not album.has_thumbnail:
            return f"Album '{album.name}' is missing thumbnail artwork"
        titles_seen: dict[str, int] = {}
        for track in album.tracks:
            key = track.title.strip().lower()
            if key in titles_seen:
                return f"Duplicate track title '{track.title}' in album '{album.name}'"
            titles_seen[key] = track.track_number
        if self.duplicate_checker:
            reason = self.duplicate_checker(album)
            if reason:
                return reason
        for track in album.tracks:
            hit = self.upload_history.find_duplicate(
                album_name=album.name,
                track_title=track.title,
                wav_byte_size=track.wav_byte_size or None,
                wav_sha256=sha256_file(track.wav_path) if track.wav_path and track.wav_path.exists() else None,
            )
            if hit:
                when = hit.get("uploaded_at") or "previously"
                return (
                    f"Duplicate DistroKid upload blocked: album '{album.name}' "
                    f"track '{track.title}' already uploaded ({when})"
                )
        return None

    def upload_albums(
        self,
        albums: list[Album],
        *,
        auto_submit: bool | None = None,
        stop_on_error: bool = False,
        headless: bool = False,
    ) -> dict[str, bool]:
        if self._is_processing:
            self._log("Already processing DistroKid uploads", "warning")
            return {}

        self._is_processing = True
        self._should_stop = False
        results: dict[str, bool] = {}
        submit = self.settings.auto_submit if auto_submit is None else bool(auto_submit)

        try:
            if self.browser is None or self.distrokid is None:
                self._log("Launching DistroKid browser…")
                if not self.connect_session(headless=headless):
                    raise DistroKidError("DistroKid login failed or timed out")

            form = self.settings.upload_form
            max_albums = max(1, int(form.max_albums_per_session or 50))
            albums_to_process = albums[:max_albums]
            if len(albums) > max_albums:
                self._log(f"Limiting to {max_albums} albums (out of {len(albums)})")

            for i, album in enumerate(albums_to_process):
                if self._should_stop:
                    self._log("Upload stopped by user")
                    break

                album_dir = str(album.path)
                if self.upload_history.is_uploaded(album_dir):
                    when = self.upload_history.get_upload_date(album_dir)
                    self._log(f"Skipping '{album.name}' — already uploaded on {when}")
                    album.status = AlbumStatus.SKIPPED
                    results[album.name] = True
                    continue

                success = self.upload_album(album, auto_submit=submit)
                results[album.name] = success
                if self._on_album_complete:
                    self._on_album_complete(album, success)

                if not success and stop_on_error:
                    break

                if success and i < len(albums_to_process) - 1:
                    delay = max(0, int(form.delay_between_albums or 0))
                    if delay:
                        self._log(f"Waiting {delay}s before next album…")
                        time.sleep(delay)

            return results
        except Exception as exc:  # noqa: BLE001
            self._log(f"Error during DistroKid upload: {exc}", "error")
            if self._on_error:
                self._on_error(str(exc))
            return results
        finally:
            if not self.settings.keep_browser_open:
                self.close()
            self._is_processing = False

    def upload_album(self, album: Album, *, auto_submit: bool = False) -> bool:
        assert self.browser is not None and self.distrokid is not None
        try:
            self._log(f"Uploading album: {album.name}")
            problem = self._validate_album_for_upload(album)
            if problem:
                self._log(problem, "warning")
                album.status = AlbumStatus.FAILED
                album.error_message = problem
                return False

            for track in album.tracks:
                track.status = TrackStatus.READY

            album.status = AlbumStatus.UPLOADING
            # DistroKid song-count question should match this album.
            try:
                self.settings.upload_form.song_count = max(1, len(album.tracks))
            except Exception:
                pass

            # Prefer channel-profile / request artist; fall back to DistroKid settings.
            if album.artist_name:
                self.settings.artist_name = album.artist_name
                if not self.settings.upload_form.apple_music_performers:
                    self.settings.upload_form.apple_music_performers = [
                        {"role": "Primary Artist", "name": album.artist_name}
                    ]
                if not self.settings.upload_form.songwriter_first_name and not self.settings.upload_form.songwriter_last_name:
                    parts = album.artist_name.split(None, 1)
                    self.settings.upload_form.songwriter_first_name = parts[0]
                    self.settings.upload_form.songwriter_last_name = parts[1] if len(parts) > 1 else ""
            elif self.settings.artist_name and not album.artist_name:
                album.artist_name = self.settings.artist_name

            self.distrokid.navigate_to_upload()

            timeout_ms = max(5, int(self.settings.upload_form.element_timeout or 30)) * 1000
            resolver = ElementResolver(self.browser.page, timeout=timeout_ms)
            form_automator = FormAutomator(
                page=self.browser.page,
                config=self.settings.upload_form,
                resolver=resolver,
                on_log=self._on_log,
                on_progress=lambda progress: self._update_progress(
                    album.name,
                    progress.completed_steps,
                    progress.total_steps,
                    progress.current_step,
                ),
            )

            success = form_automator.automate_questionnaire(album)
            if not success:
                album.status = AlbumStatus.FAILED
                album.error_message = "Form automation failed"
                return False

            if auto_submit:
                self._log("Auto-submitting DistroKid upload…")
                if not self.distrokid.submit_upload():
                    album.status = AlbumStatus.FAILED
                    album.error_message = "Form filled but submission failed"
                    self._log("Browser left open for inspection.", "warning")
                    self.settings.keep_browser_open = True
                    return False
                submitted = True
            else:
                self._log("Form ready — review and submit manually on DistroKid")
                self._log("History will NOT mark this as uploaded until you submit (or enable auto-submit).")
                submitted = False

            for track in album.tracks:
                if track.status == TrackStatus.READY:
                    track.status = TrackStatus.UPLOADED if submitted else TrackStatus.READY

            album.status = AlbumStatus.COMPLETED if submitted else AlbumStatus.UPLOADING
            track_fingerprints = []
            for track in album.tracks:
                if not track.wav_path or not track.wav_path.exists():
                    continue
                track_fingerprints.append(
                    {
                        "title": track.title,
                        "wav_byte_size": track.wav_byte_size,
                        "wav_sha256": sha256_file(track.wav_path),
                        "role": track.role,
                    }
                )

            # Only fingerprint successful DistroKid submissions — not manual review holds.
            if submitted:
                self.upload_history.record_success(
                    directory_path=str(album.path),
                    album_name=album.name,
                    track_count=len(album.tracks),
                    tracks=track_fingerprints,
                    batch_id=album.batch_id,
                )
                if self.settings.delete_wav_after_upload:
                    for track in album.tracks:
                        if track.wav_path and track.wav_path.exists():
                            try:
                                track.wav_path.unlink()
                            except OSError:
                                pass
                self._log(f"Album '{album.name}' DistroKid upload submitted")
            else:
                self._log(f"Album '{album.name}' DistroKid form ready (awaiting manual submit)")

            # Stash fingerprints for caller (remote history only when submitted).
            album.metadata = {
                "submitted": submitted,
                "track_fingerprints": track_fingerprints,
            }
            return True
        except Exception as exc:  # noqa: BLE001
            self._log(f"Error uploading album '{album.name}': {exc}", "error")
            album.status = AlbumStatus.FAILED
            album.error_message = str(exc)
            return False
