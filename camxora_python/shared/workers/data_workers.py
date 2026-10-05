"""Background workers for shell page data."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from pydantic import ValidationError

from shared.lib.disk_space import has_sufficient_free_space
from shared.lib.video_runtime_inspection import (
    ProgressRuntimePresentation,
    build_runtime_presentation_map,
    build_video_run_inspection_map,
)
from shared.models.platform import DashboardOverview, ProgressFilters, ProgressListResponse
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.services.video_workspace_service import get_video_workspace_service

if TYPE_CHECKING:
    from shared.models.platform import PendingMusicDownloadTarget
    from shared.services.workspace_cache import WorkspaceCache


# MP3 downloads are network-bound; a small pool keeps one dead/slow Suno URL
# from stalling the whole batch without hammering the CDN.
_DOWNLOAD_PARALLELISM = 4
_DOWNLOAD_TIMEOUT_S = 30.0

_HEADER_BACKFILL_LOCK = threading.Lock()
_HEADER_BACKFILL_INFLIGHT: set[str] = set()


@dataclass(frozen=True)
class _DownloadOutcome:
    ok: bool
    error: Exception | None = None


def _download_many(
    jobs: "list[tuple[str, str, str]]",
    *,
    max_workers: int = _DOWNLOAD_PARALLELISM,
) -> "list[_DownloadOutcome]":
    """Download many tracks through a bounded pool.

    ``jobs`` are ``(url, fallback_url, target_path)`` tuples. Returns one
    outcome per job, in the same order. A dead/slow URL only occupies a single
    pool slot, so it can no longer stall every other pending download the way
    the previous serial loop did.
    """
    from concurrent.futures import ThreadPoolExecutor

    outcomes = [_DownloadOutcome(False, None) for _ in jobs]
    if not jobs:
        return outcomes

    def _one(index: int, job: tuple[str, str, str]) -> tuple[int, _DownloadOutcome]:
        url, fallback_url, target_path = job
        try:
            ok = MusicDownloadSyncWorker._download_file(url, target_path)
            if not ok and fallback_url:
                from shared.services.app_logger import log_warn

                log_warn(
                    "Suno URL expired; falling back to the archived copy.",
                    category="music",
                )
                ok = MusicDownloadSyncWorker._download_file(fallback_url, target_path)
            return index, _DownloadOutcome(bool(ok), None)
        except Exception as exc:
            return index, _DownloadOutcome(False, exc)

    workers = max(1, min(int(max_workers or 1), len(jobs)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mp3-dl") as pool:
        futures = [pool.submit(_one, index, job) for index, job in enumerate(jobs)]
        for future in futures:
            index, outcome = future.result()
            outcomes[index] = outcome
    return outcomes


def _schedule_mp3_duration_header_backfill(paths: "list[str]") -> None:
    """Add Xing/Info headers in the background so downloads never wait on ffmpeg.

    Suno's CDN MP3s omit the header, so players over-report their length. The
    re-mux is best-effort and runs on a daemon thread after the sync completes,
    keeping it off the download critical path.
    """
    targets = [str(p).strip() for p in (paths or []) if str(p or "").strip()]
    if not targets:
        return

    def _run() -> None:
        from shared.lib.suno_mp3_download import ensure_mp3_duration_header

        for target in targets:
            with _HEADER_BACKFILL_LOCK:
                if target in _HEADER_BACKFILL_INFLIGHT:
                    continue
                _HEADER_BACKFILL_INFLIGHT.add(target)
            try:
                ensure_mp3_duration_header(target)
            except Exception:
                pass
            finally:
                with _HEADER_BACKFILL_LOCK:
                    _HEADER_BACKFILL_INFLIGHT.discard(target)

    threading.Thread(
        target=_run,
        name="mp3-duration-header-backfill",
        daemon=True,
    ).start()


class DashboardOverviewWorker(QThread):
    """Fetches dashboard overview off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        parent=None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._cache = cache

    def run(self) -> None:
        try:
            me = None
            profiles = None
            if self._cache is not None:
                cached_me, cached_profiles, *_ = self._cache.snapshot_core()
                me = cached_me
                profiles = cached_profiles or None
            overview = self._api.get_dashboard_overview(me=me, profiles=profiles)
            self.succeeded.emit(overview)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except ValidationError as exc:
            self.failed.emit(f"Invalid dashboard data: {exc.errors()[0]['msg']}")
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load dashboard data.")


class ProgressRowsWorker(QThread):
    """Fetches progress rows off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        filters: ProgressFilters,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._filters = filters

    def run(self) -> None:
        try:
            result = self._api.list_progress(self._filters)
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load progress rows.")


@dataclass(frozen=True, slots=True)
class WorkflowLoadResult:
    response: ProgressListResponse
    runtime_by_key: dict[str, ProgressRuntimePresentation]
    inspections: dict = field(default_factory=dict)


class WorkflowLoadWorker(QThread):
    """Fetches progress rows and desktop runtime overlays off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        filters: ProgressFilters,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._filters = filters

    def run(self) -> None:
        try:
            response = self._api.list_progress(self._filters)
            from shared.lib.progress_local_overlay import apply_local_progress_overlays

            rows = apply_local_progress_overlays(list(response.rows))
            response = response.model_copy(update={"rows": rows})
            workspace = get_video_workspace_service().get_workspace_state()
            inspections = build_video_run_inspection_map(rows)
            runtime_by_key = build_runtime_presentation_map(rows, workspace, inspections=inspections)
            self.succeeded.emit(
                WorkflowLoadResult(
                    response=response,
                    runtime_by_key=runtime_by_key,
                    inspections=inspections,
                )
            )
            from shared.lib.pipeline_completion import persist_discovered_pipeline_complete

            persist_discovered_pipeline_complete(self._api, rows, inspections)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load workflow data.")


class WorkflowRuntimeWorker(QThread):
    """Rebuilds desktop runtime overlay without refetching progress rows."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, rows: list, parent=None) -> None:
        super().__init__(parent)
        self._rows = rows

    def run(self) -> None:
        try:
            from shared.models.platform import ProgressRow

            rows = [row for row in self._rows if isinstance(row, ProgressRow)]
            workspace = get_video_workspace_service().get_workspace_state()
            runtime_by_key = build_runtime_presentation_map(rows, workspace)
            self.succeeded.emit(runtime_by_key)
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to refresh workflow runtime.")


class PendingDownloadsWorker(QThread):
    """Fetches pending desktop music downloads off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, limit: int = 12, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._limit = limit

    def run(self) -> None:
        try:
            result = self._api.list_pending_music_downloads(limit=self._limit)
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load pending downloads.")


@dataclass(frozen=True)
class MusicDownloadSyncResult:
    """Outcome of one shell music-download coordinator cycle."""

    pending_count: int = 0
    synced_count: int = 0
    error: str | None = None


class MusicDownloadSyncWorker(QThread):
    """Lists pending Suno downloads, saves MP3s, and syncs — all off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, limit: int = 24, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MusicDownloadSyncWorker")
        self._api = api
        self._limit = limit

    def run(self) -> None:
        try:
            from shared.models.platform import MusicDownloadSyncItem

            response = self._api.list_pending_music_downloads(limit=self._limit)
            from shared.lib.music_download_utils import filter_actionable_pending_downloads

            items = filter_actionable_pending_downloads(list(response.items))
            if not items:
                self.succeeded.emit(MusicDownloadSyncResult(pending_count=0, synced_count=0))
                return

            from shared.lib.device_workspace_paths import hydrate_local_suno_output_dir
            from shared.lib.music_download_utils import remap_pending_download_target

            # Hydrate device-store + push active suno root so mid-session batches
            # stop planning under a stale cloud path until the next restart.
            local_suno_base = hydrate_local_suno_output_dir(api=self._api, persist_cloud=True)

            # Phase 1 — resolve every actionable channel to a concrete target and
            # split it into "already on disk" vs "needs a network download".
            already_present: list[tuple[str, str, PendingMusicDownloadTarget]] = []
            pending_downloads: list[tuple[str, str, PendingMusicDownloadTarget, str]] = []
            ensured_dirs: set[str] = set()
            for item in items:
                for channel, target in (("primary", item.primary), ("secondary", item.secondary)):
                    if (
                        not target.download_url
                        or not target.output_dir
                        or not target.target_path
                        or target.downloaded
                    ):
                        continue
                    try:
                        # Cloud may have planned under another PC's suno root —
                        # rebase onto this machine before mkdir/download.
                        original_output = str(target.output_dir or "").strip()
                        target = remap_pending_download_target(
                            target, local_suno_base=local_suno_base
                        )
                        output_dir = str(target.output_dir or "").strip()
                        from shared.lib.path_locality import is_foreign_windows_profile_path

                        if output_dir and is_foreign_windows_profile_path(output_dir):
                            # Still foreign after remap (should be rare) —
                            # never mkdir/download into another profile.
                            from shared.services.app_logger import log_warn

                            log_warn(
                                f"Skipping pending download for task {item.task_id} "
                                f"({channel}): output_dir is under another "
                                f"Windows user profile ({output_dir})",
                                category="music",
                            )
                            continue
                        if output_dir and original_output and output_dir != original_output:
                            from shared.services.app_logger import log_info

                            log_info(
                                f"Remapped pending download {item.task_id} ({channel}) "
                                f"onto local Suno root: {output_dir}",
                                category="music",
                            )
                        if output_dir and output_dir not in ensured_dirs:
                            from shared.services.file_service import ensure_directory

                            ensure_directory(output_dir)
                            ensured_dirs.add(output_dir)
                        from pathlib import Path

                        from shared.services.file_service import sanitize_local_path

                        target_file = Path(sanitize_local_path(str(target.target_path)))
                        from shared.lib.suno_mp3_download import file_looks_like_mpeg_audio

                        if file_looks_like_mpeg_audio(target_file):
                            already_present.append((item.task_id, channel, target))
                        else:
                            pending_downloads.append(
                                (item.task_id, channel, target, str(target_file))
                            )
                    except Exception as exc:
                        # One item's bad/unreachable output_dir (e.g. a stale
                        # cross-machine path from another profile's pending
                        # download) must never abort every other pending
                        # download in this account for this cycle.
                        from shared.services.app_logger import log_error

                        log_error(
                            f"Skipping pending download for task {item.task_id} ({channel})",
                            category="music",
                            exc=exc,
                        )
                        continue

            # Phase 2 — fetch the missing files with a bounded pool. A single
            # dead/slow URL can only occupy one slot, never the whole queue.
            outcomes = _download_many(
                [(str(t.download_url), "", path) for _, _, t, path in pending_downloads]
            )

            # Phase 3 — merge outcomes and sync download state once.
            sync_map: dict[str, MusicDownloadSyncItem] = {}
            present_paths: list[str] = []

            def _record(
                task_id: str,
                channel: str,
                target: PendingMusicDownloadTarget,
                ok: bool,
            ) -> None:
                if not ok:
                    return
                present_paths.append(str(target.target_path or ""))
                current = sync_map.get(task_id) or MusicDownloadSyncItem(task_id=task_id)
                if channel == "primary":
                    sync_map[task_id] = current.model_copy(
                        update={"downloaded_primary": True, "output_dir_primary": target.output_dir}
                    )
                else:
                    sync_map[task_id] = current.model_copy(
                        update={
                            "downloaded_secondary": True,
                            "output_dir_secondary": target.output_dir,
                        }
                    )

            for task_id, channel, target in already_present:
                _record(task_id, channel, target, True)
            from shared.services.app_logger import log_error

            for (task_id, channel, target, _path), outcome in zip(pending_downloads, outcomes):
                if outcome.error is not None:
                    log_error(
                        f"Skipping pending download for task {task_id} ({channel})",
                        category="music",
                        exc=outcome.error,
                    )
                _record(task_id, channel, target, outcome.ok)

            sync_items = list(sync_map.values())
            if sync_items:
                self._api.sync_music_downloads(sync_items)

            # Phase 4 — Xing/Info headers are cosmetic; backfill them on a
            # daemon thread so they never delay the next poll cycle.
            _schedule_mp3_duration_header_backfill(present_paths)

            self.succeeded.emit(
                MusicDownloadSyncResult(pending_count=len(items), synced_count=len(sync_items))
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Music download sync failed.")

    @staticmethod
    def _download_file(url: str, target_path: str) -> bool:
        from pathlib import Path

        import httpx

        from shared.lib.suno_mp3_download import payload_is_mpeg_audio, prefer_suno_mpeg_cdn_url
        from shared.services.app_logger import log_error
        from shared.services.file_service import sanitize_local_path

        path = Path(sanitize_local_path(target_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        if not has_sufficient_free_space(path.parent):
            log_error(
                f"Not enough free disk space to download MP3, skipping: {path.parent}",
                category="music",
            )
            return False

        requested = str(url or "").strip()
        candidate = prefer_suno_mpeg_cdn_url(requested) or requested
        if not candidate:
            return False
        try:
            with httpx.Client(timeout=_DOWNLOAD_TIMEOUT_S, follow_redirects=True) as client:
                response = client.get(candidate)
                response.raise_for_status()
                content = response.content
            if not content:
                log_error(f"MP3 download returned an empty response body: {candidate}", category="music")
                return False
            if not payload_is_mpeg_audio(content):
                log_error(
                    "Suno download was not MP3 (likely m4a/Opus). Waiting for MPEG URL.",
                    category="music",
                )
                return False
            path.write_bytes(content)
        except (OSError, httpx.HTTPError) as exc:
            log_error(f"MP3 download failed: {candidate}", category="music", exc=exc)
            MusicDownloadSyncWorker._discard_empty_file(path)
            return False

        if not path.is_file() or path.stat().st_size != len(content):
            log_error(
                f"MP3 download wrote an incomplete file (disk full?): {path}",
                category="music",
            )
            MusicDownloadSyncWorker._discard_empty_file(path)
            return False
        return True

    @staticmethod
    def _discard_empty_file(path) -> None:
        try:
            if path.is_file() and path.stat().st_size == 0:
                path.unlink()
        except OSError:
            pass


@dataclass
class RunFolderRecoveryResult:
    """Outcome of moving a batch/channel's run folder and re-fetching its assets."""

    new_run_dir: str
    mp3_total: int = 0
    mp3_downloaded: int = 0
    mp3_failed: int = 0
    images_total: int = 0
    images_downloaded: int = 0
    images_failed: int = 0

    @property
    def had_any_failure(self) -> bool:
        return self.mp3_failed > 0 or self.images_failed > 0


class RunFolderRecoveryWorker(QThread):
    """Change a batch/channel's run folder and resume — without re-drafting or re-Suno.

    Repoints the server-side run folder for this row, then re-downloads already
    -successful MP3s (stable Suno URLs) and already-successful server images into the
    new folder, reusing the exact download/integrity primitives the regular sync
    workers use. Never touches drafts, lyrics, album/title, or Suno task state — this
    is a "recover from a bad/full drive mid-batch" action, not a retry of failed work.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        batch_id: str,
        profile_id: str,
        role: str,
        new_run_dir: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("RunFolderRecoveryWorker")
        self._api = api
        self._batch_id = str(batch_id or "").strip()
        self._profile_id = str(profile_id or "").strip()
        self._role = str(role or "OK").strip().upper() or "OK"
        self._new_run_dir = str(new_run_dir or "").strip()

    def run(self) -> None:
        from pathlib import Path

        from shared.lib.disk_space import get_free_bytes
        from shared.models.platform import ProgressLocalSyncItem
        from shared.services.app_logger import log_error
        from shared.services.file_service import ensure_directory, read_file_bytes, sanitize_local_path

        if not self._batch_id or not self._profile_id or not self._new_run_dir:
            self.failed.emit("Missing batch, channel, or new run folder.")
            return

        normalized_dir = sanitize_local_path(self._new_run_dir)
        if not has_sufficient_free_space(normalized_dir):
            free = get_free_bytes(normalized_dir)
            free_mb = f"{free / (1024 * 1024):.0f} MB" if free is not None else "unknown"
            self.failed.emit(
                f"Selected folder does not have enough free space ({free_mb} free). "
                "Choose a different drive/folder."
            )
            return

        try:
            ensure_directory(normalized_dir)
        except Exception as exc:
            self.failed.emit(f"Could not create the new run folder: {exc}")
            return

        result = RunFolderRecoveryResult(new_run_dir=normalized_dir)

        # 1. Repoint the server-side run folder FIRST — even if a download below fails,
        # Continue Progress / pending-download sync will look in the right place next time.
        try:
            self._api.sync_local_progress(
                [
                    ProgressLocalSyncItem(
                        batch_id=self._batch_id,
                        profile_id=self._profile_id,
                        role=self._role,
                        run_dir=normalized_dir,
                        persist_batch_run_dir=True,
                    )
                ]
            )
        except PlatformApiError as exc:
            self.failed.emit(f"Could not update the run folder on the server: {exc}")
            return

        # 2. Re-download already-successful MP3s (stable Suno URLs) into the new folder.
        try:
            from shared.models.platform import MusicDownloadSyncItem

            plan = self._api.get_batch_redownload_plan(
                batch_id=self._batch_id, role=self._role, run_dir=normalized_dir
            )
            result.mp3_total = len(plan.items)
            is_primary = self._role != "ALT"
            sync_items: list[MusicDownloadSyncItem] = []
            outcomes = _download_many(
                [
                    (item.download_url, item.fallback_download_url or "", item.target_path)
                    for item in plan.items
                ]
            )
            present_paths: list[str] = []
            for item, outcome in zip(plan.items, outcomes):
                if outcome.error is not None:
                    result.mp3_failed += 1
                    log_error(
                        f"Re-download into new run folder failed for {item.title or item.task_id}",
                        category="music",
                        exc=outcome.error,
                    )
                elif outcome.ok:
                    result.mp3_downloaded += 1
                    present_paths.append(str(item.target_path or ""))
                else:
                    result.mp3_failed += 1
                # Repoint this song's tracked output_dir/downloaded state to the new
                # folder regardless of outcome — otherwise the account-wide background
                # download sync (MusicDownloadSyncWorker) keeps retrying this exact
                # song against the *old* (bad/full) folder forever, since it reads
                # per-song output_dir/downloaded state, not the batch's run_dir.
                sync_items.append(
                    MusicDownloadSyncItem(
                        task_id=item.task_id,
                        downloaded_primary=outcome.ok if is_primary else None,
                        downloaded_secondary=outcome.ok if not is_primary else None,
                        output_dir_primary=normalized_dir if is_primary else None,
                        output_dir_secondary=normalized_dir if not is_primary else None,
                    )
                )
            if sync_items:
                try:
                    self._api.sync_music_downloads(sync_items)
                except PlatformApiError as exc:
                    log_error(
                        f"Could not sync re-downloaded state for batch {self._batch_id}",
                        category="music",
                        exc=exc,
                    )
            _schedule_mp3_duration_header_backfill(present_paths)
        except PlatformApiError as exc:
            log_error(f"Could not list MP3s to re-download for batch {self._batch_id}", category="music", exc=exc)

        # 3. Re-download already-successful images (background/thumbnail) into the new folder.
        try:
            from shared.lib.image_output_utils import ensure_image_output_local

            response = self._api.list_image_jobs(batch_id=self._batch_id, status=["success"], limit=50)
            matching = [
                job for job in response.items if str(job.channel_role or "").strip().upper() == self._role
            ]
            result.images_total = len(matching)
            for job in matching:
                source_name = str(job.output_image_path or "").strip()
                if not source_name:
                    continue
                new_path = str(Path(normalized_dir) / Path(source_name).name)
                try:
                    if read_file_bytes(new_path):
                        result.images_downloaded += 1
                        continue
                    if ensure_image_output_local(self._api, new_path, job.id):
                        result.images_downloaded += 1
                    else:
                        result.images_failed += 1
                except Exception as exc:
                    result.images_failed += 1
                    log_error(
                        f"Re-download of image job {job.id} into new run folder failed",
                        category="images",
                        exc=exc,
                    )
        except PlatformApiError as exc:
            log_error(f"Could not list images to re-download for batch {self._batch_id}", category="images", exc=exc)

        self.succeeded.emit(result)


@dataclass(slots=True)
class MissingMp3DownloadResult:
    """Outcome of downloading only missing role-scoped MP3s into the local run folder."""

    run_dir: str
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def had_any_failure(self) -> bool:
        return self.failed > 0


class MissingMp3DownloadWorker(QThread):
    """Download missing MP3s for one Progress row role — no re-draft / re-Suno.

    Uses ``batch-redownload-plan`` for existing Suno/Backblaze URLs, skips files
    already on disk, and syncs ``downloaded_*`` + ``output_dir_*`` for this role.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        batch_id: str,
        profile_id: str,
        role: str,
        run_dir: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MissingMp3DownloadWorker")
        self._api = api
        self._batch_id = str(batch_id or "").strip()
        self._profile_id = str(profile_id or "").strip()
        self._role = str(role or "OK").strip().upper() or "OK"
        self._run_dir = str(run_dir or "").strip()

    def run(self) -> None:
        from shared.lib.disk_space import get_free_bytes
        from shared.lib.missing_mp3 import filter_missing_redownload_items, target_path_is_present
        from shared.models.platform import MusicDownloadSyncItem, ProgressLocalSyncItem
        from shared.services.app_logger import log_error, log_warn
        from shared.services.file_service import ensure_directory, sanitize_local_path

        if not self._batch_id or not self._profile_id or not self._run_dir:
            self.failed.emit("Missing batch, channel, or run folder.")
            return

        from shared.lib.device_workspace_paths import local_run_dir_for_disk

        normalized_dir = local_run_dir_for_disk(sanitize_local_path(self._run_dir))
        if not normalized_dir:
            self.failed.emit("Could not resolve a local run folder on this device.")
            return

        if not has_sufficient_free_space(normalized_dir):
            free = get_free_bytes(normalized_dir)
            free_mb = f"{free / (1024 * 1024):.0f} MB" if free is not None else "unknown"
            self.failed.emit(
                f"Run folder does not have enough free space ({free_mb} free)."
            )
            return

        try:
            ensure_directory(normalized_dir)
        except Exception as exc:
            self.failed.emit(f"Could not create the local run folder: {exc}")
            return

        # Sync channel assets for this machine's folder only — do not rewrite
        # batches.ok_run_dir (legacy absolute paths stay until Change Run Folder).
        try:
            self._api.sync_local_progress(
                [
                    ProgressLocalSyncItem(
                        batch_id=self._batch_id,
                        profile_id=self._profile_id,
                        role=self._role,
                        run_dir=normalized_dir,
                        persist_batch_run_dir=False,
                    )
                ]
            )
        except PlatformApiError as exc:
            log_warn(
                f"Could not sync local run_dir assets before missing MP3 download "
                f"for batch {self._batch_id}: {exc}",
                category="music",
            )

        result = MissingMp3DownloadResult(run_dir=normalized_dir)
        try:
            plan = self._api.get_batch_redownload_plan(
                batch_id=self._batch_id, role=self._role, run_dir=normalized_dir
            )
        except PlatformApiError as exc:
            self.failed.emit(f"Could not list tracks to download: {exc}")
            return

        missing_items = filter_missing_redownload_items(list(plan.items))
        # Also count already-present plan items as skipped for the toast.
        present_count = len(plan.items) - len(missing_items)
        result.skipped = max(0, present_count)
        result.total = len(missing_items)
        if not missing_items:
            # Heal downloaded flags for files already on disk.
            sync_present: list[MusicDownloadSyncItem] = []
            is_primary = self._role != "ALT"
            for item in plan.items:
                if not target_path_is_present(item.target_path):
                    continue
                sync_present.append(
                    MusicDownloadSyncItem(
                        task_id=item.task_id,
                        downloaded_primary=True if is_primary else None,
                        downloaded_secondary=True if not is_primary else None,
                        output_dir_primary=normalized_dir if is_primary else None,
                        output_dir_secondary=normalized_dir if not is_primary else None,
                    )
                )
            if sync_present:
                try:
                    self._api.sync_music_downloads(sync_present)
                except PlatformApiError:
                    pass
            self.succeeded.emit(result)
            return

        is_primary = self._role != "ALT"
        sync_items: list[MusicDownloadSyncItem] = []
        outcomes = _download_many(
            [
                (item.download_url, item.fallback_download_url or "", item.target_path)
                for item in missing_items
            ]
        )
        present_paths: list[str] = []
        for item, outcome in zip(missing_items, outcomes):
            if outcome.error is not None:
                result.failed += 1
                log_error(
                    f"Missing MP3 download failed for {item.title or item.task_id}",
                    category="music",
                    exc=outcome.error,
                )
            elif outcome.ok:
                result.downloaded += 1
                present_paths.append(str(item.target_path or ""))
            else:
                result.failed += 1
            sync_items.append(
                MusicDownloadSyncItem(
                    task_id=item.task_id,
                    downloaded_primary=outcome.ok if is_primary else None,
                    downloaded_secondary=outcome.ok if not is_primary else None,
                    output_dir_primary=normalized_dir if is_primary else None,
                    output_dir_secondary=normalized_dir if not is_primary else None,
                )
            )
        if sync_items:
            try:
                self._api.sync_music_downloads(sync_items)
            except PlatformApiError as exc:
                log_error(
                    f"Could not sync missing-MP3 download state for batch {self._batch_id}",
                    category="music",
                    exc=exc,
                )
        _schedule_mp3_duration_header_backfill(present_paths)

        self.succeeded.emit(result)


@dataclass(frozen=True, slots=True)
class VideoPipelineOrchestrationPayload:
    rows: list
    profiles: list
    settings: dict
    workspace: object
    inspections: dict
    runtime_by_key: dict


class VideoPipelineOrchestrationWorker(QThread):
    """Loads progress, profiles, settings, and local video runtime for automation."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoPipelineOrchestrationWorker")
        self._api = api

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from features.video.services.video_local_store import VideoLocalStore
        from shared.lib.video_runtime_inspection import (
            build_runtime_presentation_map,
            build_video_run_inspection_map,
        )
        from shared.models.platform import ProgressFilters

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                future_progress = pool.submit(
                    self._api.list_progress,
                    ProgressFilters(limit=80, active_only=True),
                )
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                progress = future_progress.result()
                profiles = future_profiles.result()
                settings = future_settings.result()

            settings_raw = settings.model_dump() if hasattr(settings, "model_dump") else dict(settings or {})
            store = VideoLocalStore()
            workspace = store.read_workspace_state(settings_raw)
            active = get_video_workspace_service().get_workspace_state()
            if active is not None and (active.export.running or active.export.merge_running):
                workspace = workspace.model_copy(update={"export": active.export})

            rows = list(progress.rows)
            from shared.lib.progress_local_overlay import apply_local_progress_overlays

            rows = apply_local_progress_overlays(rows)
            inspections = build_video_run_inspection_map(rows)
            runtime_by_key = build_runtime_presentation_map(rows, workspace, inspections=inspections)
            self.succeeded.emit(
                VideoPipelineOrchestrationPayload(
                    rows=rows,
                    profiles=list(profiles),
                    settings=settings_raw,
                    workspace=workspace,
                    inspections=inspections,
                    runtime_by_key=runtime_by_key,
                )
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Video pipeline orchestration failed.")


class SettingsWorker(QThread):
    """Fetches shared settings off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        try:
            result = self._api.get_settings()
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load settings.")


class ManualInspectionWorker(QThread):
    """Inspects manual image folders for progress rows off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, rows: list, parent=None) -> None:
        super().__init__(parent)
        self._rows = rows

    def run(self) -> None:
        try:
            from shared.lib.manual_asset_paths import ManualAssetInspection, inspect_manual_asset_files, manual_inspection_key
            from shared.models.platform import ProgressRow
            from shared.services.file_service import list_directory_image_paths

            inspections: dict[str, ManualAssetInspection] = {}
            for row in self._rows:
                if not isinstance(row, ProgressRow):
                    continue
                directory = str(row.meta.run_dir or "").strip()
                if not directory:
                    continue
                files = list_directory_image_paths(directory, max_results=50)
                key = manual_inspection_key(row.meta.batch_id, row.meta.profile_id, row.meta.role)
                inspections[key] = inspect_manual_asset_files(directory, files)
            self.succeeded.emit(inspections)
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to inspect manual asset folders.")


class SyncManualImageWorker(QThread):
    """Syncs manual image assets for a batch off the UI thread."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id

    def run(self) -> None:
        try:
            result = self._api.sync_manual_image_jobs(self._batch_id)
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to sync manual image assets.")


@dataclass(frozen=True, slots=True)
class MusicWorkspacePayload:
    profiles: list
    settings: object
    description_options: list
    structure_options: list
    mood_options: list
    history: object
    operation_costs: object
    language_options: list
    youtube_connections: list
    suno_blocklist: object | None = None


class MusicWorkspaceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    WORKSPACE_TIMEOUT = 90.0

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        previous_timeout = self._api._client._default_timeout
        self._api._client._default_timeout = self.WORKSPACE_TIMEOUT
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                future_descriptions = pool.submit(self._api.list_prompt_description_names)
                future_structures = pool.submit(self._api.list_prompt_structure_names)
                future_moods = pool.submit(self._api.list_prompt_mood_names)
                future_history = pool.submit(self._api.list_music_history, limit=25)
                future_costs = pool.submit(self._fetch_operation_costs)
                future_languages = pool.submit(self._fetch_language_options)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                future_blocklist = pool.submit(self._fetch_suno_blocklist)
                profiles = future_profiles.result()
                settings = future_settings.result()
                description_options = future_descriptions.result()
                structure_options = future_structures.result()
                mood_options = future_moods.result()
                history = future_history.result()
                operation_costs = future_costs.result()
                language_options = future_languages.result()
                youtube_connections = future_youtube.result()
                suno_blocklist = future_blocklist.result()
            self.succeeded.emit(
                MusicWorkspacePayload(
                    profiles=profiles,
                    settings=settings,
                    description_options=description_options,
                    structure_options=structure_options,
                    mood_options=mood_options,
                    history=history,
                    operation_costs=operation_costs,
                    language_options=language_options,
                    youtube_connections=youtube_connections,
                    suno_blocklist=suno_blocklist,
                )
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load music workspace.")
        finally:
            self._api._client._default_timeout = previous_timeout

    def _fetch_operation_costs(self):
        from shared.models.platform import OperationCostsResponse

        try:
            return self._api.get_operation_costs()
        except Exception:
            return OperationCostsResponse(items=[])

    def _fetch_language_options(self):
        from shared.lib.music_settings import DEFAULT_LANGUAGE_OPTIONS, language_options_from_response

        try:
            response = self._api.list_music_languages()
            options = language_options_from_response(response.items)
            if options:
                return options
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to load music languages from API: %s",
                exc,
            )
        return list(DEFAULT_LANGUAGE_OPTIONS)

    def _fetch_suno_blocklist(self):
        from shared.models.platform import SunoBlocklistRuntimeResponse

        try:
            return self._api.get_suno_blocklist()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to load Suno blocklist from API: %s",
                exc,
            )
            return SunoBlocklistRuntimeResponse()


class MusicLanguagesWorker(QThread):
    """Fetch enabled music languages — lightweight refresh for the settings strip."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        from shared.lib.music_settings import DEFAULT_LANGUAGE_OPTIONS, language_options_from_response

        try:
            response = self._api.list_music_languages()
            options = language_options_from_response(response.items)
            if not options:
                options = list(DEFAULT_LANGUAGE_OPTIONS)
            self.succeeded.emit(options)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load music languages.")


class MusicHistoryRefreshWorker(QThread):
    """Fetch only music history — used for live batch progress updates."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, limit: int = 25, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MusicHistoryRefreshWorker")
        self._api = api
        self._limit = max(1, min(100, int(limit)))
        self._from_date = ""
        self._to_date = ""

    def set_date_filters(self, *, from_date: str = "", to_date: str = "") -> None:
        self._from_date = str(from_date or "").strip()
        self._to_date = str(to_date or "").strip()

    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._api.list_music_history(
                    limit=self._limit,
                    from_date=self._from_date or None,
                    to_date=self._to_date or None,
                )
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to refresh music history.")


class PatchSettingsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, patch: dict[str, object], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PatchSettingsWorker")
        self._api = api
        self._patch = patch

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.patch_settings(self._patch))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to save settings.")


class DraftGenerationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, payload: dict, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._payload = payload

    def run(self) -> None:
        from shared.lib.music_composer import DraftPoolSeedState, build_history_avoid_lists, build_reservation_token
        from shared.models.platform import DraftGenerationRequest, MusicHistoryBatch

        claimed: list[tuple[str, object]] = []
        payload = self._payload
        try:
            history_batches = payload.get("history_batches") or []
            if not isinstance(history_batches, list):
                history_batches = []
            batches = [batch for batch in history_batches if isinstance(batch, MusicHistoryBatch)]
            avoid_lists = build_history_avoid_lists(batches, int(payload["history_window"]))
            reservation_token = build_reservation_token()

            pool_seeds = None
            if payload.get("use_content_pools"):
                def claim(kind: str):
                    response = self._api.claim_content_pool_item(kind, reservation_token=reservation_token)
                    claimed.append((kind, response.item))
                    return response.item

                title_seed = claim("titles")
                album_seed = claim("albums")
                opening_seed = claim("openings") if payload.get("unique_opening") else None
                pool_seeds = DraftPoolSeedState(
                    title_seed=title_seed.text,
                    album_seed=album_seed.text,
                    opening_seed=(
                        "\n".join(part for part in (opening_seed.text, opening_seed.secondary_text) if part)
                        if opening_seed
                        else None
                    ),
                )

            draft = self._api.generate_draft(
                DraftGenerationRequest(
                    language=str(payload["language"]),
                    secondary_language=payload.get("secondary_language") or None,
                    creativity_level=int(payload["creativity"]),
                    description=str(payload["description"]),
                    structure=str(payload.get("structure") or ""),
                    description_id=payload.get("description_id"),
                    structure_id=payload.get("structure_id"),
                    mood_id=payload.get("mood_id"),
                    structure_mode=str(payload.get("structure_mode") or "template"),
                    avoid_titles=avoid_lists["titles"],
                    avoid_albums=avoid_lists["albums"],
                    avoid_openings=avoid_lists["openings"],
                    title_seed=pool_seeds.title_seed if pool_seeds else None,
                    album_seed=pool_seeds.album_seed if pool_seeds else None,
                    forced_opening=pool_seeds.opening_seed if pool_seeds else None,
                    channel_profile_id=payload.get("channel_profile_id"),
                )
            )
            for kind, item in claimed:
                self._api.finalize_content_pool_item(
                    kind,
                    item_id=item.id,
                    reservation_token=item.reservation_token,
                )
            self.succeeded.emit({"draft": draft, "pool_seeds": pool_seeds})
        except Exception as exc:
            for kind, item in claimed:
                try:
                    self._api.release_content_pool_item(
                        kind,
                        item_id=item.id,
                        reservation_token=item.reservation_token,
                    )
                except PlatformApiError:
                    pass
            self.failed.emit(str(exc) or "Failed to generate draft.")


class PolishLyricsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, payload: dict, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._payload = payload

    def run(self) -> None:
        from shared.models.platform import LyricsPolishRequest

        try:
            result = self._api.polish_lyrics(
                LyricsPolishRequest(
                    lyrics=str(self._payload["lyrics"]),
                    strength=int(self._payload["strength"]),
                    channel_profile_id=self._payload.get("channel_profile_id"),
                    batch_id=self._payload.get("batch_id"),
                    song_id=self._payload.get("song_id"),
                    title=self._payload.get("title"),
                    album=self._payload.get("album"),
                    mood=self._payload.get("mood"),
                    mood_id=self._payload.get("mood_id"),
                    structure=self._payload.get("structure"),
                    structure_id=self._payload.get("structure_id"),
                )
            )
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to polish lyrics.")


class MusicPlanPreflightWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, payload, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._payload = payload

    def run(self) -> None:
        from shared.models.platform import MusicPlanPreflightRequest

        try:
            request = (
                self._payload
                if isinstance(self._payload, MusicPlanPreflightRequest)
                else MusicPlanPreflightRequest.model_validate(self._payload)
            )
            result = self._api.preflight_music_plan(request)
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to validate generation plan.")


class CreateBatchesWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, requests: list, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._requests = requests

    def run(self) -> None:
        from shared.lib.music_batch_plan import create_planned_batches
        from shared.models.platform import BatchCreateRequest

        planned = [item for item in self._requests if isinstance(item, BatchCreateRequest)]
        if not planned:
            self.failed.emit("No batch runs to create.")
            return
        try:
            from_date = min(str(item.from_date) for item in planned)
            to_date = max(str(item.to_date or item.from_date) for item in planned)
            history = self._api.list_music_history(
                limit=100,
                from_date=from_date,
                to_date=to_date,
            )
            result = create_planned_batches(
                self._api.create_batch,
                planned,
                existing_batches=list(history.batches or []),
            )
            if result.has_progress:
                self.succeeded.emit(result)
                return
            if result.failed:
                from shared.lib.music_batch_plan import format_failed_create_slots

                suffix = "s" if result.failed_count != 1 else ""
                detail = format_failed_create_slots(result.failed)
                self.failed.emit(
                    f"Could not create {result.failed_count} batch run{suffix}: {detail}"
                )
                return
            self.failed.emit("No batch runs to create.")
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to create batch.")


class BatchStatusWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.get_batch_status(self._batch_id))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load batch status.")


class RetrySongDraftWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_id: str, song_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._song_id = song_id

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.retry_song_draft(self._batch_id, self._song_id))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to retry draft generation.")


class RewriteBatchAlbumWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        *,
        role: str = "ok",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._role = role

    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._api.rewrite_batch_album(self._batch_id, role=self._role)
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to rewrite album.")


class RewriteSongTitleWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        song_id: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._song_id = song_id

    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._api.rewrite_song_title(self._batch_id, self._song_id)
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to rewrite title.")


class RetrySongSunoWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        song_id: str,
        *,
        title: str | None = None,
        album: str | None = None,
        lyrics: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._song_id = song_id
        self._title = title
        self._album = album
        self._lyrics = lyrics

    def run(self) -> None:
        try:
            self.succeeded.emit(
                self._api.retry_song_suno(
                    self._batch_id,
                    self._song_id,
                    title=self._title,
                    album=self._album,
                    lyrics=self._lyrics,
                )
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to retry Suno submission.")


class BatchRetryDraftsWorker(QThread):
    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        song_ids: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._song_ids = list(song_ids)

    def run(self) -> None:
        if not self._song_ids:
            self.failed.emit("No failed drafts to retry.")
            return
        queued = 0
        last_error = ""
        for song_id in self._song_ids:
            try:
                self._api.retry_song_draft(self._batch_id, song_id)
                queued += 1
            except PlatformApiError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc) or "Failed to retry draft generation."
        if queued <= 0:
            self.failed.emit(last_error or "Failed to retry draft generation.")
            return
        self.succeeded.emit(queued)


class BatchRetrySunoWorker(QThread):
    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        song_ids: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._song_ids = list(song_ids)

    def run(self) -> None:
        if not self._song_ids:
            self.failed.emit("No failed Suno submissions to retry.")
            return
        queued = 0
        last_error = ""
        for song_id in self._song_ids:
            try:
                self._api.retry_song_suno(self._batch_id, song_id)
                queued += 1
            except PlatformApiError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc) or "Failed to retry Suno submission."
        if queued <= 0:
            self.failed.emit(last_error or "Failed to retry Suno submission.")
            return
        self.succeeded.emit(queued)


class DeleteFailedBatchWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.delete_batch(self._batch_id))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to delete batch.")


class BatchRetryFailuresWorker(QThread):
    """Queue draft and Suno retries for all failed songs in one batch."""

    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        batch_id: str,
        draft_ids: list[str],
        suno_ids: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_id = batch_id
        self._draft_ids = list(draft_ids)
        self._suno_ids = list(suno_ids)

    def run(self) -> None:
        if not self._draft_ids and not self._suno_ids:
            self.failed.emit("No failed songs to retry.")
            return
        queued = 0
        last_error = ""
        for song_id in self._draft_ids:
            try:
                self._api.retry_song_draft(self._batch_id, song_id)
                queued += 1
            except PlatformApiError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc) or "Failed to retry draft generation."
        for song_id in self._suno_ids:
            try:
                self._api.retry_song_suno(self._batch_id, song_id)
                queued += 1
            except PlatformApiError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc) or "Failed to retry Suno submission."
        if queued <= 0:
            self.failed.emit(last_error or "Failed to retry batch.")
            return
        self.succeeded.emit(queued)


class PipelineRecoveryWorker(QThread):
    """Recover failed pipeline songs: draft retry, Suno retry, or rewrite→Suno."""

    succeeded = Signal(object)
    failed = Signal(str)
    progressed = Signal(str)

    def __init__(self, api: PlatformApi, targets: list, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PipelineRecoveryWorker")
        self._api = api
        self._targets = list(targets)

    def run(self) -> None:
        from shared.models.platform import LyricsPolishRequest

        if not self._targets:
            self.failed.emit("No failed songs to recover.")
            return

        draft_ok = 0
        suno_ok = 0
        rewrite_ok = 0
        skipped = 0
        last_error = ""
        total = len(self._targets)
        for index, target in enumerate(self._targets, start=1):
            kind = str(getattr(target, "kind", "") or "")
            batch_id = str(getattr(target, "batch_id", "") or "")
            song_id = str(getattr(target, "song_id", "") or "")
            reason = str(getattr(target, "reason", "") or "")
            label = f"{kind}:{reason}" if reason else kind
            self.progressed.emit(f"Recovering {index}/{total} ({label})…")
            try:
                if kind == "skip":
                    skipped += 1
                    continue
                if kind == "draft":
                    self._api.retry_song_draft(batch_id, song_id)
                    draft_ok += 1
                elif kind == "suno_rewrite":
                    lyrics = str(getattr(target, "lyrics", "") or "").strip()
                    channel_id = str(getattr(target, "channel_profile_id", "") or "").strip() or None
                    if not lyrics or not channel_id:
                        self._api.retry_song_suno(batch_id, song_id)
                        suno_ok += 1
                        continue
                    response = self._api.polish_lyrics(
                        LyricsPolishRequest(
                            lyrics=lyrics,
                            strength=75,
                            channel_profile_id=channel_id,
                            batch_id=batch_id,
                            song_id=song_id,
                            title=getattr(target, "title", None),
                            album=getattr(target, "album", None),
                            mood_id=getattr(target, "mood_id", None),
                            structure_id=getattr(target, "structure_id", None),
                        )
                    )
                    rewrite_ok += 1
                    if not bool(getattr(response, "suno_queued", False)):
                        self._api.retry_song_suno(batch_id, song_id)
                        suno_ok += 1
                else:
                    self._api.retry_song_suno(batch_id, song_id)
                    suno_ok += 1
            except PlatformApiError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc) or "Recovery step failed."

        recovered = draft_ok + suno_ok + rewrite_ok
        if recovered <= 0 and skipped <= 0:
            self.failed.emit(last_error or "Failed to recover pipeline songs.")
            return
        self.succeeded.emit(
            {
                "recovered": recovered,
                "draft": draft_ok,
                "suno": suno_ok,
                "rewrite": rewrite_ok,
                "skipped": skipped,
                "total": total,
                "last_error": last_error,
            }
        )


@dataclass(frozen=True, slots=True)
class PipelineRecoveryScanResult:
    """Outcome of one background pipeline-recovery scan cycle."""

    candidate_count: int = 0
    recovered: int = 0
    draft: int = 0
    suno: int = 0
    rewrite: int = 0
    skipped: int = 0
    attempted_targets: tuple = ()


class PipelineRecoveryScanWorker(QThread):
    """Fetch recent history, select failed songs, and run recovery."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        history_limit: int = 25,
        max_targets: int = 3,
        target_filter=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PipelineRecoveryScanWorker")
        self._api = api
        self._history_limit = max(1, min(100, int(history_limit)))
        self._max_targets = max(1, min(20, int(max_targets)))
        self._target_filter = target_filter

    def run(self) -> None:
        from features.music.lib.pipeline_recovery import collect_recovery_targets
        from shared.models.platform import LyricsPolishRequest

        try:
            history = self._api.list_music_history(limit=self._history_limit)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load music history for recovery.")
            return

        candidates = collect_recovery_targets(list(history.batches or []))
        if self._target_filter is not None:
            try:
                candidates = list(self._target_filter(candidates) or [])
            except Exception as exc:
                self.failed.emit(str(exc) or "Recovery filter failed.")
                return
        targets = candidates[: self._max_targets]
        if not targets:
            self.succeeded.emit(
                PipelineRecoveryScanResult(candidate_count=len(candidates))
            )
            return

        draft_ok = 0
        suno_ok = 0
        rewrite_ok = 0
        skipped = 0
        for target in targets:
            kind = str(getattr(target, "kind", "") or "")
            batch_id = str(getattr(target, "batch_id", "") or "")
            song_id = str(getattr(target, "song_id", "") or "")
            try:
                if kind == "skip":
                    skipped += 1
                    continue
                if kind == "draft":
                    self._api.retry_song_draft(batch_id, song_id)
                    draft_ok += 1
                elif kind == "suno_rewrite":
                    lyrics = str(getattr(target, "lyrics", "") or "").strip()
                    channel_id = (
                        str(getattr(target, "channel_profile_id", "") or "").strip() or None
                    )
                    if not lyrics or not channel_id:
                        self._api.retry_song_suno(batch_id, song_id)
                        suno_ok += 1
                        continue
                    response = self._api.polish_lyrics(
                        LyricsPolishRequest(
                            lyrics=lyrics,
                            strength=75,
                            channel_profile_id=channel_id,
                            batch_id=batch_id,
                            song_id=song_id,
                            title=getattr(target, "title", None),
                            album=getattr(target, "album", None),
                            mood_id=getattr(target, "mood_id", None),
                            structure_id=getattr(target, "structure_id", None),
                        )
                    )
                    rewrite_ok += 1
                    if not bool(getattr(response, "suno_queued", False)):
                        self._api.retry_song_suno(batch_id, song_id)
                        suno_ok += 1
                else:
                    self._api.retry_song_suno(batch_id, song_id)
                    suno_ok += 1
            except Exception:
                continue

        recovered = draft_ok + suno_ok + rewrite_ok
        self.succeeded.emit(
            PipelineRecoveryScanResult(
                candidate_count=len(candidates),
                recovered=recovered,
                draft=draft_ok,
                suno=suno_ok,
                rewrite=rewrite_ok,
                skipped=skipped,
                attempted_targets=tuple(targets),
            )
        )


@dataclass(frozen=True, slots=True)
class ImageWorkspacePayload:
    me: object
    profiles: list
    progress: object
    image_jobs: object
    settings: object
    music_history: object


class ImageWorkspaceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, history_limit: int = 25, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._history_limit = history_limit

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        from shared.models.platform import ProgressFilters

        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                future_me = pool.submit(self._api.get_me)
                future_profiles = pool.submit(self._api.list_profiles)
                future_progress = pool.submit(
                    self._api.list_progress,
                    ProgressFilters(limit=25, active_only=False),
                )
                future_jobs = pool.submit(self._api.list_image_jobs, limit=200)
                future_settings = pool.submit(self._api.get_settings)
                future_history = pool.submit(self._api.list_music_history, limit=self._history_limit)
                image_jobs = future_jobs.result()
                settings = future_settings.result()
                self.succeeded.emit(
                    ImageWorkspacePayload(
                        me=future_me.result(),
                        profiles=future_profiles.result(),
                        progress=future_progress.result(),
                        image_jobs=image_jobs,
                        settings=settings,
                        music_history=future_history.result(),
                    )
                )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load image workspace.")


class ImageRetryJobsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        job_ids: list[str] | None = None,
        batch_id: str | None = None,
        force: bool = False,
        settings_patch: dict[str, object] | None = None,
        run_after_retry: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._job_ids = list(job_ids or [])
        self._batch_id = batch_id
        self._force = bool(force)
        self._settings_patch = dict(settings_patch or {})
        self._run_after_retry = run_after_retry

    def run(self) -> None:
        from shared.models.platform import ImageJobsRetryRequest, ImageJobsRunRequest
        from shared.services.app_logger import log_info

        try:
            if not self._job_ids and not self._batch_id:
                raise PlatformApiError("No image jobs selected for retry.")
            if self._settings_patch:
                self._api.patch_settings(self._settings_patch)
            target = (
                f"batch {self._batch_id}"
                if self._batch_id and not self._job_ids
                else f"{len(self._job_ids)} job(s)"
            )
            action = "Regenerating" if self._force else "Retrying"
            log_info(f"{action} image jobs for {target}…", category="image")
            response = self._api.retry_image_jobs(
                ImageJobsRetryRequest(
                    job_ids=self._job_ids or None,
                    batch_id=self._batch_id,
                    force=self._force,
                )
            )
            updated = int(getattr(response, "updated", 0) or 0)
            if updated <= 0:
                log_info("Image retry reset 0 jobs.", category="image")
            else:
                log_info(f"Image retry reset {updated} job(s).", category="image")
            if self._run_after_retry and self._batch_id:
                # API also schedules a drain after retry; keep this as a fallback.
                self._api.run_image_jobs(
                    ImageJobsRunRequest(batch_id=self._batch_id, limit=50)
                )
            self.succeeded.emit(response)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to retry image jobs.")


class ImageManualGenerateWorker(QThread):
    succeeded = Signal(object)  # ImageJobsManualGenerateResponse
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        kind: str,
        prompt: str | None,
        channel_profile_id: str | None,
        settings_patch: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._kind = kind
        self._prompt = prompt
        self._channel_profile_id = channel_profile_id
        self._settings_patch = dict(settings_patch or {})

    def run(self) -> None:
        from shared.models.platform import ImageJobsManualGenerateRequest
        from shared.services.app_logger import log_info

        try:
            if self._settings_patch:
                self._api.patch_settings(self._settings_patch)
            kind = "thumbnail" if self._kind == "thumbnail" else "background"
            log_info(
                f"Manual Generation creating Not available queue row ({kind})…",
                category="image",
            )
            response = self._api.manual_generate_image_jobs(
                ImageJobsManualGenerateRequest(
                    kind=kind,
                    prompt=self._prompt,
                    channel_profile_id=self._channel_profile_id,
                )
            )
            self.succeeded.emit(response)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to create Manual Generation row.")


class EnqueueImageJobsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_ids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_ids = list(batch_ids)

    def run(self) -> None:
        from shared.models.platform import ImageJobsRunRequest
        from shared.services.app_logger import log_info

        try:
            if not self._batch_ids:
                raise PlatformApiError("No batches selected for image enqueue.")
            log_info(
                f"Enqueueing images for {len(self._batch_ids)} batch(es)…",
                category="image",
            )
            response = self._api.enqueue_image_jobs(self._batch_ids)
            for batch_id in self._batch_ids:
                self._api.run_image_jobs(
                    ImageJobsRunRequest(batch_id=batch_id, limit=50)
                )
            self.succeeded.emit(response)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to enqueue image jobs.")


class ImageClearQueueWorker(QThread):
    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, batch_ids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._batch_ids = batch_ids

    def run(self) -> None:
        from shared.models.platform import ImageJobsClearRequest

        try:
            deleted = 0
            for batch_id in self._batch_ids:
                response = self._api.clear_image_jobs(ImageJobsClearRequest(batch_id=batch_id))
                deleted += response.deleted
            self.succeeded.emit(deleted)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to clear image queue.")


class ImagePreviewLoadWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        api: PlatformApi | None = None,
        bg_path: str | None,
        th_path: str | None,
        bg_job_id: str | None = None,
        th_job_id: str | None = None,
        bg_updated_at: str | None = None,
        th_updated_at: str | None = None,
        footer_detail: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._bg_path = bg_path
        self._th_path = th_path
        self._bg_job_id = bg_job_id
        self._th_job_id = th_job_id
        self._bg_updated_at = bg_updated_at
        self._th_updated_at = th_updated_at
        self._footer_detail = footer_detail

    def run(self) -> None:
        from shared.services.file_service import read_file_bytes

        try:
            self.succeeded.emit(
                {
                    "bg_bytes": self._load_image_bytes(
                        self._bg_path, self._bg_job_id, self._bg_updated_at
                    ),
                    "th_bytes": self._load_image_bytes(
                        self._th_path, self._th_job_id, self._th_updated_at
                    ),
                    "footer_detail": self._footer_detail,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load image previews.")

    def _load_image_bytes(
        self,
        path: str | None,
        job_id: str | None,
        remote_updated_at: str | None = None,
    ) -> bytes | None:
        from shared.lib.image_output_utils import ensure_image_output_local
        from shared.services.file_service import read_file_bytes

        local_path = ensure_image_output_local(
            self._api,
            path,
            job_id,
            remote_updated_at=remote_updated_at,
        )
        return read_file_bytes(local_path) if local_path else None


class ImageOutputSyncWorker(QThread):
    """Download successful image jobs from the API when files are missing or stale locally."""

    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, limit: int = 40, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ImageOutputSyncWorker")
        self._api = api
        self._limit = limit

    def run(self) -> None:
        from shared.lib.image_output_utils import (
            ensure_image_output_local,
            resolve_local_image_output_path,
        )

        try:
            response = self._api.list_image_jobs(status=["success"], limit=self._limit)
            synced = 0
            for job in response.items:
                target_path = resolve_local_image_output_path(job.output_image_path)
                if not target_path:
                    continue
                before = Path(target_path)
                before_mtime = before.stat().st_mtime if before.is_file() else None
                before_size = before.stat().st_size if before.is_file() else None
                local_path = ensure_image_output_local(
                    self._api,
                    job.output_image_path,
                    job.id,
                    remote_updated_at=getattr(job, "updated_at", None),
                )
                if not local_path:
                    continue
                after = Path(local_path)
                if not after.is_file():
                    continue
                after_mtime = after.stat().st_mtime
                after_size = after.stat().st_size
                if before_mtime is None or before_size != after_size or after_mtime != before_mtime:
                    synced += 1
            self.succeeded.emit(synced)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Image output sync failed.")


class ImageOpenWorker(QThread):
    """Ensure an image output exists locally, then open it in the system viewer."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        path: str,
        job_id: str,
        remote_updated_at: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._path = path
        self._job_id = job_id
        self._remote_updated_at = remote_updated_at

    def run(self) -> None:
        from shared.lib.image_output_utils import ensure_image_output_local

        try:
            local_path = ensure_image_output_local(
                self._api,
                self._path,
                self._job_id,
                remote_updated_at=self._remote_updated_at,
            )
            if not local_path:
                self.failed.emit("Image file is not available yet.")
                return
            self.succeeded.emit(local_path)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to open image file.")


class ProgressLocalSyncWorker(QThread):
    """Detect local run-folder truth ahead of API metadata and sync it back."""

    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProgressLocalSyncWorker")
        self._api = api

    def run(self) -> None:
        from shared.lib.progress_local_overlay import apply_local_progress_overlays
        from shared.lib.progress_local_sync import build_local_progress_sync_items
        from shared.models.platform import ProgressFilters, ProgressLocalSyncItem

        try:
            response = self._api.list_progress(ProgressFilters(limit=80, active_only=True))
            rows = apply_local_progress_overlays(list(response.rows))
            local_items = build_local_progress_sync_items(rows)
            if not local_items:
                self.succeeded.emit(0)
                return
            payload = [
                ProgressLocalSyncItem(
                    batch_id=item.batch_id,
                    profile_id=item.profile_id,
                    role=item.role,
                    run_dir=item.run_dir,
                    long_ready=item.long_ready,
                    reel_ready=item.reel_ready,
                    local_mp3_count=item.local_mp3_count,
                    expected=item.expected,
                    background_16x9_path=item.background_16x9_path,
                    background_9x16_path=item.background_9x16_path,
                    thumbnail_16x9_path=item.thumbnail_16x9_path,
                    thumbnail_9x16_path=item.thumbnail_9x16_path,
                    pipeline_complete=item.pipeline_complete,
                )
                for item in local_items
            ]
            result = self._api.sync_local_progress(payload)
            self.succeeded.emit(int(result.updated or 0))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Progress local sync failed.")


@dataclass(frozen=True, slots=True)
class MyPromptMutationResult:
    kind: str
    deleted: bool
    item: dict[str, object] | None = None
    prompt_id: str = ""

    @property
    def descriptions(self) -> bool:
        return self.kind == "description"


class MyPromptMutationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        kind: str,
        creating: bool = False,
        prompt_id: str = "",
        name: str = "",
        content: str = "",
        delete: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._kind = kind
        self._creating = creating
        self._prompt_id = prompt_id
        self._name = name
        self._content = content
        self._delete = delete

    def run(self) -> None:
        try:
            if self._delete:
                if self._kind == "description":
                    self._api.delete_my_description(self._prompt_id)
                elif self._kind == "mood":
                    self._api.delete_my_mood(self._prompt_id)
                else:
                    self._api.delete_my_structure(self._prompt_id)
                self.succeeded.emit(
                    MyPromptMutationResult(
                        kind=self._kind,
                        deleted=True,
                        prompt_id=self._prompt_id,
                    )
                )
                return
            if self._kind == "description":
                if self._creating:
                    saved = self._api.create_my_description(name=self._name, content=self._content)
                else:
                    saved = self._api.update_my_description(
                        self._prompt_id,
                        name=self._name,
                        content=self._content,
                    )
            elif self._kind == "mood":
                if self._creating:
                    saved = self._api.create_my_mood(name=self._name, content=self._content)
                else:
                    saved = self._api.update_my_mood(
                        self._prompt_id,
                        name=self._name,
                        content=self._content,
                    )
            elif self._creating:
                saved = self._api.create_my_structure(name=self._name, content=self._content)
            else:
                saved = self._api.update_my_structure(
                    self._prompt_id,
                    name=self._name,
                    content=self._content,
                )
            item = saved if isinstance(saved, dict) else None
            self.succeeded.emit(
                MyPromptMutationResult(
                    kind=self._kind,
                    deleted=False,
                    item=item,
                )
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to update custom prompt.")


@dataclass(frozen=True, slots=True)
class SettingsWorkspacePayload:
    me: object
    profiles: list
    settings: object
    description_options: list
    structure_options: list
    mood_options: list
    youtube_connections: list


class SettingsWorkspaceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        try:
            with ThreadPoolExecutor(max_workers=7) as pool:
                future_me = pool.submit(self._api.get_me)
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                future_descriptions = pool.submit(self._api.list_prompt_description_names)
                future_structures = pool.submit(self._api.list_prompt_structure_names)
                future_moods = pool.submit(self._api.list_prompt_mood_names)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                self.succeeded.emit(
                    SettingsWorkspacePayload(
                        me=future_me.result(),
                        profiles=future_profiles.result(),
                        settings=future_settings.result(),
                        description_options=future_descriptions.result(),
                        structure_options=future_structures.result(),
                        mood_options=future_moods.result(),
                        youtube_connections=future_youtube.result(),
                    )
                )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load settings workspace.")


class SaveProfileWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        profile_id: str | None,
        payload: dict[str, object],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._profile_id = profile_id
        self._payload = payload

    def run(self) -> None:
        from shared.models.auth import CreateProfileRequest, UpdateProfileRequest

        try:
            if self._profile_id:
                result = self._api.update_profile(
                    self._profile_id,
                    UpdateProfileRequest.model_validate(self._payload),
                )
            else:
                result = self._api.create_profile(CreateProfileRequest.model_validate(self._payload))
            self.succeeded.emit(result)
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to save profile.")


@dataclass(frozen=True, slots=True)
class ProfileMediaCacheResult:
    profile_id: str
    logo_path: str | None = None
    cover_path: str | None = None


class ProfileMediaCacheWorker(QThread):
    """Downloads a profile's server logo/cover into the local cache off the UI thread.

    Selecting a profile in Settings used to call this synchronously — a real,
    multi-megabyte network download blocking the entire UI on every profile
    switch whenever the file wasn't cached yet, and hanging hard on any slow
    or unreliable connection to the API. This mirrors the existing
    SamplePackInstallWorker pattern so the UI updates the moment the download
    finishes instead of freezing until it does.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        profile_id: str,
        cache_dir,
        need_logo: bool,
        need_cover: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ProfileMediaCacheWorker")
        self._api = api
        self._profile_id = profile_id
        self._cache_dir = cache_dir
        self._need_logo = need_logo
        self._need_cover = need_cover

    def run(self) -> None:
        logo_path: str | None = None
        cover_path: str | None = None
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            if self._need_logo:
                logo_path = self._download(
                    lambda: self._api.download_profile_logo(self._profile_id),
                    self._cache_dir / "logo.png",
                )
            if self._need_cover:
                cover_path = self._download(
                    lambda: self._api.download_profile_cover(self._profile_id, 0),
                    self._cache_dir / "cover.png",
                )
            self.succeeded.emit(
                ProfileMediaCacheResult(
                    profile_id=self._profile_id,
                    logo_path=logo_path,
                    cover_path=cover_path,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to download profile media.")

    @staticmethod
    def _download(fetch, destination) -> str | None:
        try:
            raw = fetch()
        except PlatformApiError:
            return None
        except Exception:
            return None
        if not raw:
            return None
        destination.write_bytes(raw)
        return str(destination)


class DeleteProfileWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, profile_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._profile_id = profile_id

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.delete_profile(self._profile_id))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to delete profile.")


class YouTubeActionWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, action: str, *, profile_id: str = "", session_id: str = "", channel_id: str = "", parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._action = action
        self._profile_id = profile_id
        self._session_id = session_id
        self._channel_id = channel_id

    def run(self) -> None:
        try:
            if self._action == "start":
                self.succeeded.emit(self._api.start_youtube_connection(self._profile_id))
            elif self._action == "disconnect":
                self.succeeded.emit(self._api.disconnect_youtube_connection(self._profile_id))
            elif self._action == "resync":
                self.succeeded.emit(self._api.resync_youtube_connection(self._profile_id))
            elif self._action == "select":
                self.succeeded.emit(self._api.select_youtube_channel(self._session_id, self._channel_id))
            else:
                raise RuntimeError(f"Unsupported YouTube action: {self._action}")
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "YouTube action failed.")


class ContentPoolWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, kind: str, *, offset: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._kind = kind
        self._offset = offset

    def run(self) -> None:
        try:
            stats = self._api.get_content_pool_stats()
            items = self._api.list_content_pool_items(self._kind, limit=50, offset=self._offset)
            self.succeeded.emit({"stats": stats, "items": items})
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load content pools.")


class YouTubePlaylistsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, profile_id: str, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._profile_id = profile_id

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.list_youtube_playlists(self._profile_id))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load YouTube playlists.")


class YouTubeConnectionsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.list_youtube_connections())
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load YouTube connections.")


class ImageSamplePacksWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.list_image_sample_packs())
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load image sample packs.")


class VideoWorkspaceWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoWorkspaceWorker")
        self._api = api

    def run(self) -> None:
        from features.video.services.video_local_store import VideoLocalStore

        try:
            settings_response = self._api.get_settings()
            settings = settings_response.model_dump(by_alias=True)
            store = VideoLocalStore()
            workspace = store.read_workspace_state(settings)
            self.succeeded.emit((workspace, settings))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load video workspace.")


class VideoPatchTemplateWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        store,
        patch: dict[str, object],
        *,
        settings: dict[str, object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("VideoPatchTemplateWorker")
        self._store = store
        self._patch = patch
        self._settings = settings

    def run(self) -> None:
        try:
            workspace = self._store.patch_template(self._patch, settings=self._settings)
            self.succeeded.emit(workspace)
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to save video template.")


class ProfileSetupContextWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, parent=None) -> None:
        super().__init__(parent)
        self._api = api

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from shared.lib.music_composer import read_settings_dict

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                future_settings = pool.submit(self._api.get_settings)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                settings_raw = read_settings_dict(future_settings.result())
                youtube_connections = future_youtube.result()
            self.succeeded.emit((settings_raw, youtube_connections))
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load profile setup context.")


class SamplePackInstallWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, url: str, destination_dir: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url
        self._destination_dir = destination_dir

    def run(self) -> None:
        from shared.services.sample_pack_installer import SamplePackInstaller

        try:
            result = SamplePackInstaller().install(self._url, self._destination_dir)
            if not result.ok:
                self.failed.emit(result.error or "Unable to install sample pack.")
                return
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc) or "Unable to install sample pack.")


class WorkspacePushRefreshWorker(QThread):
    """Refetch workspace data after a server push notification."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        cache: WorkspaceCache,
        *,
        scope: str = "workspace",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("WorkspacePushRefreshWorker")
        self._api = api
        self._cache = cache
        self._scope = scope

    def run(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from shared.lib.music_composer import read_settings_dict

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                profiles = future_profiles.result()
                settings_raw = read_settings_dict(future_settings.result())
                youtube_connections = future_youtube.result()

            self._cache.apply_warmup(profiles=profiles, settings_raw=settings_raw)
            self._cache.apply_settings_workspace(
                settings_raw=settings_raw,
                youtube_connections=youtube_connections,
            )
            self.succeeded.emit(
                {
                    "scope": self._scope,
                    "settings_raw": settings_raw,
                }
            )
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to refresh workspace after push.")
