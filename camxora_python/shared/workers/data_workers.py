"""Background workers for shell page data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from pydantic import ValidationError

from shared.lib.video_runtime_inspection import ProgressRuntimePresentation, build_runtime_presentation_map
from shared.models.platform import DashboardOverview, ProgressFilters, ProgressListResponse
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.services.video_workspace_service import get_video_workspace_service

if TYPE_CHECKING:
    from shared.services.workspace_cache import WorkspaceCache


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
            runtime_by_key = build_runtime_presentation_map(rows, workspace)
            self.succeeded.emit(WorkflowLoadResult(response=response, runtime_by_key=runtime_by_key))
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

            sync_map: dict[str, MusicDownloadSyncItem] = {}
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
                    output_dir = str(target.output_dir or "").strip()
                    if output_dir and output_dir not in ensured_dirs:
                        from shared.services.file_service import ensure_directory

                        ensure_directory(output_dir)
                        ensured_dirs.add(output_dir)
                    from pathlib import Path

                    from shared.services.file_service import sanitize_local_path

                    target_file = Path(sanitize_local_path(str(target.target_path)))
                    target_path = str(target_file)
                    if target_file.is_file() and target_file.stat().st_size > 0:
                        downloaded = True
                    else:
                        downloaded = self._download_file(target.download_url, target_path)
                    if not downloaded:
                        continue
                    current = sync_map.get(item.task_id) or MusicDownloadSyncItem(task_id=item.task_id)
                    if channel == "primary":
                        sync_map[item.task_id] = current.model_copy(
                            update={"downloaded_primary": True, "output_dir_primary": target.output_dir}
                        )
                    else:
                        sync_map[item.task_id] = current.model_copy(
                            update={
                                "downloaded_secondary": True,
                                "output_dir_secondary": target.output_dir,
                            }
                        )

            sync_items = list(sync_map.values())
            if sync_items:
                self._api.sync_music_downloads(sync_items)

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

        from shared.services.file_service import sanitize_local_path

        path = Path(sanitize_local_path(target_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                path.write_bytes(response.content)
            return True
        except (OSError, httpx.HTTPError):
            return False


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
            runtime_by_key = build_runtime_presentation_map(rows, workspace)
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
            with ThreadPoolExecutor(max_workers=6) as pool:
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                future_descriptions = pool.submit(self._api.list_prompt_description_names)
                future_structures = pool.submit(self._api.list_prompt_structure_names)
                future_history = pool.submit(self._api.list_music_history, limit=8)
                future_costs = pool.submit(self._fetch_operation_costs)
                future_languages = pool.submit(self._fetch_language_options)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                future_blocklist = pool.submit(self._fetch_suno_blocklist)
                profiles = future_profiles.result()
                settings = future_settings.result()
                description_options = future_descriptions.result()
                structure_options = future_structures.result()
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

    def __init__(self, api: PlatformApi, *, limit: int = 8, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._limit = limit

    def run(self) -> None:
        try:
            self.succeeded.emit(self._api.list_music_history(limit=self._limit))
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
                    description=self._payload.get("description"),
                    structure=self._payload.get("structure"),
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
        from shared.models.platform import BatchCreateRequest

        try:
            results = []
            for request in self._requests:
                if not isinstance(request, BatchCreateRequest):
                    continue
                response = self._api.create_batch(request)
                results.append(response)
            self.succeeded.emit(results)
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
        run_after_retry: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._job_ids = list(job_ids or [])
        self._batch_id = batch_id
        self._run_after_retry = run_after_retry

    def run(self) -> None:
        from shared.models.platform import ImageJobsRetryRequest, ImageJobsRunRequest
        from shared.services.app_logger import log_info

        try:
            if not self._job_ids and not self._batch_id:
                raise PlatformApiError("No image jobs selected for retry.")
            target = (
                f"batch {self._batch_id}"
                if self._batch_id and not self._job_ids
                else f"{len(self._job_ids)} job(s)"
            )
            log_info(f"Retrying image jobs for {target}…", category="image")
            response = self._api.retry_image_jobs(
                ImageJobsRetryRequest(
                    job_ids=self._job_ids or None,
                    batch_id=self._batch_id,
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
        footer_detail: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._bg_path = bg_path
        self._th_path = th_path
        self._bg_job_id = bg_job_id
        self._th_job_id = th_job_id
        self._footer_detail = footer_detail

    def run(self) -> None:
        from shared.services.file_service import read_file_bytes

        try:
            self.succeeded.emit(
                {
                    "bg_bytes": self._load_image_bytes(self._bg_path, self._bg_job_id),
                    "th_bytes": self._load_image_bytes(self._th_path, self._th_job_id),
                    "footer_detail": self._footer_detail,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to load image previews.")

    def _load_image_bytes(self, path: str | None, job_id: str | None) -> bytes | None:
        from shared.lib.image_output_utils import ensure_image_output_local
        from shared.services.file_service import read_file_bytes

        local_path = ensure_image_output_local(self._api, path, job_id)
        return read_file_bytes(local_path) if local_path else None


class ImageOutputSyncWorker(QThread):
    """Download successful image jobs from the API when files are missing locally."""

    succeeded = Signal(int)
    failed = Signal(str)

    def __init__(self, api: PlatformApi, *, limit: int = 40, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ImageOutputSyncWorker")
        self._api = api
        self._limit = limit

    def run(self) -> None:
        from shared.lib.image_output_utils import ensure_image_output_local
        from shared.services.file_service import read_file_bytes, sanitize_local_path

        try:
            response = self._api.list_image_jobs(status=["success"], limit=self._limit)
            synced = 0
            for job in response.items:
                target_path = sanitize_local_path(str(job.output_image_path or "").strip())
                if not target_path or read_file_bytes(target_path):
                    continue
                if ensure_image_output_local(self._api, job.output_image_path, job.id):
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
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._path = path
        self._job_id = job_id

    def run(self) -> None:
        from shared.lib.image_output_utils import ensure_image_output_local

        try:
            local_path = ensure_image_output_local(self._api, self._path, self._job_id)
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
    descriptions: bool
    deleted: bool
    item: dict[str, object] | None = None
    prompt_id: str = ""


class MyPromptMutationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        *,
        descriptions: bool,
        creating: bool = False,
        prompt_id: str = "",
        name: str = "",
        content: str = "",
        delete: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._descriptions = descriptions
        self._creating = creating
        self._prompt_id = prompt_id
        self._name = name
        self._content = content
        self._delete = delete

    def run(self) -> None:
        try:
            if self._delete:
                if self._descriptions:
                    self._api.delete_my_description(self._prompt_id)
                else:
                    self._api.delete_my_structure(self._prompt_id)
                self.succeeded.emit(
                    MyPromptMutationResult(
                        descriptions=self._descriptions,
                        deleted=True,
                        prompt_id=self._prompt_id,
                    )
                )
                return
            if self._descriptions:
                if self._creating:
                    saved = self._api.create_my_description(name=self._name, content=self._content)
                else:
                    saved = self._api.update_my_description(
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
                    descriptions=self._descriptions,
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
            with ThreadPoolExecutor(max_workers=6) as pool:
                future_me = pool.submit(self._api.get_me)
                future_profiles = pool.submit(self._api.list_profiles)
                future_settings = pool.submit(self._api.get_settings)
                future_descriptions = pool.submit(self._api.list_prompt_description_names)
                future_structures = pool.submit(self._api.list_prompt_structure_names)
                future_youtube = pool.submit(self._api.list_youtube_connections)
                self.succeeded.emit(
                    SettingsWorkspacePayload(
                        me=future_me.result(),
                        profiles=future_profiles.result(),
                        settings=future_settings.result(),
                        description_options=future_descriptions.result(),
                        structure_options=future_structures.result(),
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
