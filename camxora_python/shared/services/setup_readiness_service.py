"""Global setup readiness state for the header notification bell."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from shared.lib.music_readiness import MusicReadinessReport, build_music_readiness_report
from shared.models.auth import ProfileResponse
from shared.models.platform import YouTubeConnectionResponse
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache


class SetupReadinessService(QObject):
    report_changed = Signal(object)

    _instance: SetupReadinessService | None = None

    def __init__(self) -> None:
        super().__init__()
        self._report: MusicReadinessReport | None = None

    @classmethod
    def instance(cls) -> SetupReadinessService:
        if cls._instance is None:
            cls._instance = SetupReadinessService()
        return cls._instance

    @property
    def report(self) -> MusicReadinessReport | None:
        return self._report

    def incomplete_count(self) -> int:
        if self._report is None:
            return 0
        return sum(1 for item in self._report.items if not item.complete)

    def refresh_from_cache(self, cache: WorkspaceCache | None) -> None:
        if cache is None:
            self._apply_report(None)
            return
        _me, profiles, settings_raw, *_rest = cache.snapshot_core()
        connections, _fetched_at = cache.snapshot_settings_extras()
        if not profiles:
            self._apply_report(None)
            return
        from shared.services.workspace_defaults_sync import ensure_workspace_defaults

        settings = ensure_workspace_defaults(settings_raw=dict(settings_raw or {}), cache=cache, persist=False)
        report = build_music_readiness_report(
            profiles=[item for item in profiles if isinstance(item, ProfileResponse)],
            settings=settings,
            youtube_connections=self._normalize_youtube_connections(connections),
        )
        self._apply_report(report)

    def refresh_async(self, api: PlatformApi, cache: WorkspaceCache, *, parent: QObject | None = None) -> None:
        from shared.workers.data_workers import ProfileSetupContextWorker

        worker = ProfileSetupContextWorker(api, parent=parent)
        worker.succeeded.connect(lambda payload: self._on_async_payload(payload, cache, api))
        worker.failed.connect(lambda _message: self.refresh_from_cache(cache))
        worker.start()

    def _on_async_payload(self, payload: object, cache: WorkspaceCache, api: PlatformApi | None = None) -> None:
        if isinstance(payload, tuple) and len(payload) == 2:
            settings_raw, youtube_connections = payload
            if isinstance(settings_raw, dict):
                from shared.services.workspace_defaults_sync import ensure_workspace_defaults

                merged = ensure_workspace_defaults(
                    settings_raw=settings_raw,
                    api=api,
                    cache=cache,
                    persist=True,
                )
                cache.apply_settings_workspace(
                    settings_raw=merged,
                    youtube_connections=self._normalize_youtube_connections(
                        list(youtube_connections) if isinstance(youtube_connections, list) else []
                    ),
                )
        self.refresh_from_cache(cache)

    def _apply_report(self, report: MusicReadinessReport | None) -> None:
        self._report = report
        self.report_changed.emit(report)

    @staticmethod
    def _normalize_youtube_connections(items: list[object]) -> list[YouTubeConnectionResponse]:
        normalized: list[YouTubeConnectionResponse] = []
        for item in items:
            if isinstance(item, YouTubeConnectionResponse):
                normalized.append(item)
            elif isinstance(item, dict):
                try:
                    normalized.append(YouTubeConnectionResponse.model_validate(item))
                except Exception:
                    continue
        return normalized


def refresh_setup_readiness(
    *,
    api: PlatformApi | None = None,
    cache: WorkspaceCache | None = None,
    parent: QObject | None = None,
    force_network: bool = False,
) -> None:
    """Refresh header notification checklist from cache, optionally re-fetching settings."""
    service = SetupReadinessService.instance()
    if force_network and api is not None and cache is not None:
        service.refresh_async(api, cache, parent=parent)
        return
    service.refresh_from_cache(cache)
