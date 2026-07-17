"""Shared workspace data preloaded during startup — reused across pages."""



from __future__ import annotations



import threading

import time

from dataclasses import dataclass, field

from typing import Any



from shared.models.auth import ProfileResponse, UserMeResponse
from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import DashboardOverview, PromptNameOption



DEFAULT_PAGE_CACHE_TTL_SECONDS = 120.0





def cache_entry_is_fresh(fetched_at: float, ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS) -> bool:

    return fetched_at > 0 and (time.time() - fetched_at) < ttl





@dataclass(slots=True)

class WorkspaceCache:

    """Thread-safe cache for data every heavy workspace page needs."""



    me: UserMeResponse | None = None

    profiles: list[ProfileResponse] = field(default_factory=list)

    settings_raw: dict[str, Any] = field(default_factory=dict)

    description_options: list[PromptNameOption] = field(default_factory=list)

    structure_options: list[PromptNameOption] = field(default_factory=list)

    language_options: list[tuple[str, str]] = field(default_factory=list)

    warmed_at: float = 0.0

    dashboard_overview: DashboardOverview | None = None

    dashboard_fetched_at: float = 0.0

    youtube_connections: list[Any] = field(default_factory=list)

    my_description_items: list[Any] = field(default_factory=list)

    my_structure_items: list[Any] = field(default_factory=list)

    settings_workspace_fetched_at: float = 0.0

    content_pool_payloads: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)

    content_pool_fetched_at: dict[tuple[str, int], float] = field(default_factory=dict)

    image_sample_packs: list[Any] = field(default_factory=list)

    image_sample_packs_fetched_at: float = 0.0

    sample_library_scans: dict[tuple[str, str], tuple[list[str], list[str]]] = field(default_factory=dict)

    sample_library_scan_fetched_at: dict[tuple[str, str], float] = field(default_factory=dict)

    video_workspace: VideoWorkspaceState | None = None

    video_settings_raw: dict[str, Any] = field(default_factory=dict)

    video_fetched_at: float = 0.0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)



    def clear(self) -> None:
        """Drop all cached workspace data (required on logout / account switch)."""
        with self._lock:
            self.me = None
            self.profiles = []
            self.settings_raw = {}
            self.description_options = []
            self.structure_options = []
            self.language_options = []
            self.warmed_at = 0.0
            self.dashboard_overview = None
            self.dashboard_fetched_at = 0.0
            self.youtube_connections = []
            self.my_description_items = []
            self.my_structure_items = []
            self.settings_workspace_fetched_at = 0.0
            self.content_pool_payloads = {}
            self.content_pool_fetched_at = {}
            self.image_sample_packs = []
            self.image_sample_packs_fetched_at = 0.0
            self.sample_library_scans = {}
            self.sample_library_scan_fetched_at = {}
            self.video_workspace = None
            self.video_settings_raw = {}
            self.video_fetched_at = 0.0

    def has_core(self) -> bool:

        with self._lock:

            return bool(self.profiles) and bool(self.settings_raw)



    def apply_warmup(

        self,

        *,

        me: UserMeResponse | None = None,

        profiles: list[ProfileResponse] | None = None,

        settings_raw: dict[str, Any] | None = None,

        description_options: list[PromptNameOption] | None = None,

        structure_options: list[PromptNameOption] | None = None,

        language_options: list[tuple[str, str]] | None = None,

    ) -> None:

        with self._lock:

            if me is not None:

                self.me = me

            if profiles is not None:

                self.profiles = list(profiles)

            if settings_raw is not None:

                self.settings_raw = dict(settings_raw)

            if description_options is not None:

                self.description_options = list(description_options)

            if structure_options is not None:

                self.structure_options = list(structure_options)

            if language_options is not None:

                self.language_options = list(language_options)

            self.warmed_at = time.time()



    def get_language_options(self) -> list[tuple[str, str]]:

        with self._lock:

            return list(self.language_options)



    def snapshot_core(self) -> tuple[

        UserMeResponse | None,

        list[ProfileResponse],

        dict[str, Any],

        list[PromptNameOption],

        list[PromptNameOption],

    ]:

        with self._lock:

            return (

                self.me,

                list(self.profiles),

                dict(self.settings_raw),

                list(self.description_options),

                list(self.structure_options),

            )



    def apply_dashboard(self, overview: DashboardOverview) -> None:

        with self._lock:

            self.dashboard_overview = overview

            self.dashboard_fetched_at = time.time()

            self.me = overview.me

            self.profiles = list(overview.profiles)



    def snapshot_dashboard(self) -> DashboardOverview | None:

        with self._lock:

            return self.dashboard_overview



    def is_dashboard_fresh(self, ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS) -> bool:

        with self._lock:

            return self.dashboard_overview is not None and cache_entry_is_fresh(self.dashboard_fetched_at, ttl)



    def apply_settings_workspace(

        self,

        *,

        me: UserMeResponse | None = None,

        profiles: list[ProfileResponse] | None = None,

        settings_raw: dict[str, Any] | None = None,

        description_options: list[PromptNameOption] | None = None,

        structure_options: list[PromptNameOption] | None = None,

        youtube_connections: list[Any] | None = None,

        my_description_items: list[Any] | None = None,

        my_structure_items: list[Any] | None = None,

    ) -> None:

        with self._lock:

            if me is not None:

                self.me = me

            if profiles is not None:

                self.profiles = list(profiles)

            if settings_raw is not None:

                self.settings_raw = dict(settings_raw)

            if description_options is not None:

                self.description_options = list(description_options)

            if structure_options is not None:

                self.structure_options = list(structure_options)

            if youtube_connections is not None:

                self.youtube_connections = list(youtube_connections)

            if my_description_items is not None:

                self.my_description_items = list(my_description_items)

            if my_structure_items is not None:

                self.my_structure_items = list(my_structure_items)

            self.settings_workspace_fetched_at = time.time()

            self.warmed_at = self.settings_workspace_fetched_at



    def snapshot_settings_extras(self) -> tuple[list[Any], float]:

        with self._lock:

            return list(self.youtube_connections), self.settings_workspace_fetched_at



    def snapshot_my_prompt_items(self) -> tuple[list[Any], list[Any], float]:

        with self._lock:

            return (
                list(self.my_description_items),
                list(self.my_structure_items),
                self.settings_workspace_fetched_at,
            )



    def is_settings_workspace_fresh(self, ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS) -> bool:

        with self._lock:

            return (

                bool(self.profiles)

                and bool(self.settings_raw)

                and self.settings_workspace_fetched_at > 0

                and cache_entry_is_fresh(self.settings_workspace_fetched_at, ttl)

            )



    def apply_content_pool(self, kind: str, offset: int, payload: dict[str, Any]) -> None:

        key = (kind, offset)

        with self._lock:

            self.content_pool_payloads[key] = payload

            self.content_pool_fetched_at[key] = time.time()



    def snapshot_content_pool(self, kind: str, offset: int) -> dict[str, Any] | None:

        key = (kind, offset)

        with self._lock:

            return self.content_pool_payloads.get(key)



    def is_content_pool_fresh(

        self,

        kind: str,

        offset: int,

        ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS,

    ) -> bool:

        key = (kind, offset)

        with self._lock:

            fetched_at = self.content_pool_fetched_at.get(key, 0.0)

            return key in self.content_pool_payloads and cache_entry_is_fresh(fetched_at, ttl)



    def apply_image_sample_packs(self, packs: list[Any]) -> None:

        with self._lock:

            self.image_sample_packs = list(packs)

            self.image_sample_packs_fetched_at = time.time()



    def snapshot_image_sample_packs(self) -> list[Any]:

        with self._lock:

            return list(self.image_sample_packs)



    def is_image_sample_packs_fresh(self, ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS) -> bool:

        with self._lock:

            return bool(self.image_sample_packs) and cache_entry_is_fresh(self.image_sample_packs_fetched_at, ttl)



    def apply_sample_library_scan(

        self,

        bg_dir: str,

        th_dir: str,

        *,

        bg_files: list[str],

        th_files: list[str],

    ) -> None:

        key = (bg_dir, th_dir)

        with self._lock:

            self.sample_library_scans[key] = (list(bg_files), list(th_files))

            self.sample_library_scan_fetched_at[key] = time.time()



    def snapshot_sample_library_scan(self, bg_dir: str, th_dir: str) -> tuple[list[str], list[str]] | None:

        key = (bg_dir, th_dir)

        with self._lock:

            return self.sample_library_scans.get(key)



    def is_sample_library_scan_fresh(

        self,

        bg_dir: str,

        th_dir: str,

        ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS,

    ) -> bool:

        key = (bg_dir, th_dir)

        with self._lock:

            fetched_at = self.sample_library_scan_fetched_at.get(key, 0.0)

            return key in self.sample_library_scans and cache_entry_is_fresh(fetched_at, ttl)

    def apply_video_workspace(
        self,
        workspace: VideoWorkspaceState,
        settings_raw: dict[str, Any],
    ) -> None:
        with self._lock:
            self.video_workspace = workspace
            self.video_settings_raw = dict(settings_raw)
            self.video_fetched_at = time.time()

    def invalidate_video_workspace(self) -> None:
        """Drop cached video workspace so the next load re-reads local templates."""
        with self._lock:
            self.video_workspace = None
            self.video_settings_raw = {}
            self.video_fetched_at = 0.0

    def snapshot_video_workspace(self) -> tuple[VideoWorkspaceState | None, dict[str, Any]]:
        with self._lock:
            return self.video_workspace, dict(self.video_settings_raw)

    def has_video_workspace(self) -> bool:
        with self._lock:
            return self.video_workspace is not None and bool(self.video_settings_raw)

    def is_video_workspace_fresh(self, ttl: float = DEFAULT_PAGE_CACHE_TTL_SECONDS) -> bool:
        with self._lock:
            return self.video_workspace is not None and cache_entry_is_fresh(self.video_fetched_at, ttl)

    @staticmethod

    def settings_to_raw(settings: object) -> dict[str, Any]:

        if hasattr(settings, "model_dump"):

            return settings.model_dump(by_alias=True)  # type: ignore[union-attr]

        if isinstance(settings, dict):

            return settings

        return {}


