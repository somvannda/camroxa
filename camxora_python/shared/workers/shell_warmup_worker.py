"""Preload shared workspace data while the startup screen is visible."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal

from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.platform import PromptNameOption
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.services.workspace_cache import WorkspaceCache


class ShellWarmupWorker(QThread):
    progress = Signal(str, str, int)
    succeeded = Signal()
    failed = Signal(str)

    def __init__(
        self,
        api: PlatformApi,
        cache: WorkspaceCache,
        *,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ShellWarmupWorker")
        self._api = api
        self._cache = cache

    def run(self) -> None:
        try:
            self.progress.emit("Preparing workspace", "Loading profiles and settings.", 60)
            me, profiles, settings_raw, descriptions, structures = self._cache.snapshot_core()
            tasks: dict[str, object] = {}

            with ThreadPoolExecutor(max_workers=6) as pool:
                if me is None:
                    tasks["me"] = pool.submit(self._api.get_me)
                if not profiles:
                    tasks["profiles"] = pool.submit(self._api.list_profiles)
                if not settings_raw:
                    tasks["settings"] = pool.submit(self._api.get_settings)
                if not descriptions:
                    tasks["descriptions"] = pool.submit(self._api.list_prompt_description_names)
                if not structures:
                    tasks["structures"] = pool.submit(self._api.list_prompt_structure_names)
                tasks["languages"] = pool.submit(self._fetch_language_options)

                self.progress.emit("Preparing workspace", "Fetching studio data in parallel.", 72)

                if "me" in tasks:
                    me = tasks["me"].result()  # type: ignore[union-attr]
                if "profiles" in tasks:
                    profiles = tasks["profiles"].result()  # type: ignore[union-attr]
                if "settings" in tasks:
                    settings = tasks["settings"].result()  # type: ignore[union-attr]
                    settings_raw = WorkspaceCache.settings_to_raw(settings)
                if "descriptions" in tasks:
                    descriptions = tasks["descriptions"].result()  # type: ignore[union-attr]
                if "structures" in tasks:
                    structures = tasks["structures"].result()  # type: ignore[union-attr]
                language_options = tasks["languages"].result()  # type: ignore[union-attr]

            self.progress.emit("Preparing workspace", "Loading dashboard overview.", 80)
            self._cache.apply_warmup(
                me=me,
                profiles=[item for item in profiles if isinstance(item, ProfileResponse)],
                settings_raw=settings_raw,
                description_options=[item for item in descriptions if isinstance(item, PromptNameOption)],
                structure_options=[item for item in structures if isinstance(item, PromptNameOption)],
                language_options=language_options,
            )
            if isinstance(me, UserMeResponse) and isinstance(settings_raw, dict):
                from shared.services.workspace_prefs_sync import pull_workspace_prefs_from_settings

                pull_workspace_prefs_from_settings(str(me.id), settings_raw)
            # Prefetch Home/Profile data before the shell appears.
            if not self._cache.is_dashboard_fresh() and isinstance(me, UserMeResponse):
                try:
                    overview = self._api.get_dashboard_overview(
                        me=me,
                        profiles=[item for item in profiles if isinstance(item, ProfileResponse)],
                    )
                    self._cache.apply_dashboard(overview)
                except Exception:
                    pass
            self._preload_video_workspace(settings_raw)
            self.progress.emit("Preparing workspace", "Loading settings workspace.", 85)
            self._preload_settings_workspace(
                me=me,
                profiles=[item for item in profiles if isinstance(item, ProfileResponse)],
                settings_raw=settings_raw if isinstance(settings_raw, dict) else {},
                description_options=[item for item in descriptions if isinstance(item, PromptNameOption)],
                structure_options=[item for item in structures if isinstance(item, PromptNameOption)],
            )
            self.progress.emit("Opening studio", "Building workspace pages.", 90)
            self.succeeded.emit()
        except PlatformApiError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Failed to prepare workspace.")

    def _fetch_language_options(self) -> list[tuple[str, str]]:
        from shared.lib.music_settings import DEFAULT_LANGUAGE_OPTIONS, language_options_from_response

        try:
            response = self._api.list_music_languages()
            options = language_options_from_response(response.items)
            if options:
                return options
        except Exception:
            pass
        return list(DEFAULT_LANGUAGE_OPTIONS)

    def _preload_video_workspace(self, settings_raw: dict) -> None:
        if not settings_raw:
            return
        from features.video.services.video_local_store import VideoLocalStore

        workspace = VideoLocalStore().read_workspace_state(settings_raw)
        self._cache.apply_video_workspace(workspace, settings_raw)

    def _preload_settings_workspace(
        self,
        *,
        me: object,
        profiles: list[ProfileResponse],
        settings_raw: dict,
        description_options: list[PromptNameOption],
        structure_options: list[PromptNameOption],
    ) -> None:
        if not profiles or not settings_raw:
            return
        if self._cache.is_settings_workspace_fresh():
            return
        from shared.models.auth import UserMeResponse

        with ThreadPoolExecutor(max_workers=3) as pool:
            future_youtube = pool.submit(self._api.list_youtube_connections)
            future_descriptions = pool.submit(self._api.list_my_descriptions)
            future_structures = pool.submit(self._api.list_my_structures)
            youtube_connections = future_youtube.result()
            my_description_items = future_descriptions.result()
            my_structure_items = future_structures.result()

        self._cache.apply_settings_workspace(
            me=me if isinstance(me, UserMeResponse) else None,
            profiles=profiles,
            settings_raw=settings_raw,
            description_options=description_options,
            structure_options=structure_options,
            youtube_connections=youtube_connections,
            my_description_items=my_description_items,
            my_structure_items=my_structure_items,
        )
