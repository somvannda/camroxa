"""PersistenceCoordinator — owns startup/persistence orchestration.

Uses dependency injection to avoid direct MainWindow references.
"""
from __future__ import annotations

from typing import Any, Callable

from ..ports import EventBusPort, LoggerPort

from ...database.music_migrate import ensure_database_and_migrate
from ...database.persistence import (
    DbCfg,
    db_cfg_from_env,
    db_list_profiles,
    db_list_saved_texts,
    db_load_music_app_data,
    db_patch_settings,
)
from ...models.music_model import normalize_music_app_data


class PersistenceCoordinator:
    """Owns startup/persistence orchestration extracted from MainWindow.

    All host dependencies are injected via constructor parameters so the
    coordinator is instantiable without a QApplication.
    """

    def __init__(
        self,
        *,
        db_cfg_accessor: Callable[[], Any],
        db_cfg_setter: Callable[[Any], None],
        settings_accessor: Callable[[], dict],
        music_data_accessor: Callable[[], dict],
        music_data_setter: Callable[[dict], None],
        settings_setter: Callable[[dict], None],
        restore_music_runtime_state_fn: Callable[[], None],
        restore_runtime_state_fn: Callable[[], None],
        logger: LoggerPort | None = None,
        bus: EventBusPort | None = None,
        db_cfg: DbCfg | None = None,
    ) -> None:
        if db_cfg_accessor is None:
            raise ValueError("PersistenceCoordinator requires a non-None db_cfg_accessor")
        if db_cfg_setter is None:
            raise ValueError("PersistenceCoordinator requires a non-None db_cfg_setter")
        if settings_accessor is None:
            raise ValueError("PersistenceCoordinator requires a non-None settings_accessor")
        if music_data_accessor is None:
            raise ValueError("PersistenceCoordinator requires a non-None music_data_accessor")
        if music_data_setter is None:
            raise ValueError("PersistenceCoordinator requires a non-None music_data_setter")
        if settings_setter is None:
            raise ValueError("PersistenceCoordinator requires a non-None settings_setter")
        if restore_music_runtime_state_fn is None:
            raise ValueError("PersistenceCoordinator requires a non-None restore_music_runtime_state_fn")
        if restore_runtime_state_fn is None:
            raise ValueError("PersistenceCoordinator requires a non-None restore_runtime_state_fn")
        self._db_cfg_accessor = db_cfg_accessor
        self._db_cfg_setter = db_cfg_setter
        self._settings_accessor = settings_accessor
        self._music_data_accessor = music_data_accessor
        self._music_data_setter = music_data_setter
        self._settings_setter = settings_setter
        self._restore_music_runtime_state_fn = restore_music_runtime_state_fn
        self._restore_runtime_state_fn = restore_runtime_state_fn
        self._logger = logger
        self._bus = bus
        self._db_cfg: DbCfg | None = db_cfg
        self._db_startup_message: str = ""

    def update_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update the database configuration after a reconnection."""
        self._db_cfg = cfg
        self._db_cfg_setter(cfg)

    def initialize_database(self) -> None:
        """Run database/bootstrap initialization workflow."""
        import time

        cfg = db_cfg_from_env()
        self._db_cfg_setter(cfg)
        self._db_startup_message = ""
        if cfg:
            migrate_result = ensure_database_and_migrate(cfg)
            if not bool(migrate_result.get("ok", False)):
                self._db_startup_message = str(migrate_result.get("message", "Database migration failed"))
                if self._logger:
                    self._logger.error(f"[{time.strftime('%H:%M:%S')}] Database init FAILED: {self._db_startup_message}")
                self._db_cfg_setter(None)
            else:
                if self._logger:
                    self._logger.info(f"[{time.strftime('%H:%M:%S')}] Database initialized: {cfg.host}:{cfg.port}/{cfg.database}")
        else:
            self._db_startup_message = "Database .env is not configured"
            if self._logger:
                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Database not configured: .env file missing or incomplete")

    def load_persisted_data(self) -> None:
        """Load persisted application state."""
        self._hydrate_from_database()

    def _hydrate_from_database(self) -> dict:
        db_cfg = self._db_cfg_accessor()
        raw = db_load_music_app_data(db_cfg)
        music_data = normalize_music_app_data(raw)
        if db_cfg:
            try:
                music_data["profiles"] = db_list_profiles(db_cfg)
            except Exception:
                music_data.setdefault("profiles", [])
        self._music_data_setter(music_data)
        self._settings_setter(dict(music_data.get("settings") or {}))
        return music_data

    def reload_music_db_collections(self) -> None:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return
        try:
            music_data = self._music_data_accessor()
            music_data["profiles"] = db_list_profiles(db_cfg)
            descriptions = db_list_saved_texts(db_cfg, "descriptions")
            structures = db_list_saved_texts(db_cfg, "structures")
            if descriptions:
                music_data["descriptions"] = descriptions
            if structures:
                music_data["structures"] = structures
            self._music_data_setter(music_data)
        except Exception as exc:
            if self._logger:
                import time
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Database collection refresh failed: {exc}")

    def apply_settings_patch(self, patch: dict) -> dict:
        db_cfg = self._db_cfg_accessor()
        current = {**self._settings_accessor(), **(patch or {})}
        if db_cfg:
            saved = db_patch_settings(db_cfg, patch or {})
            if isinstance(saved, dict):
                current = {**current, **saved}
        music_data = self._music_data_accessor()
        music_data["settings"] = current
        self._music_data_setter(music_data)
        self._settings_setter(dict(current))
        return current

    def reload_persisted_state(self) -> dict:
        data = self._hydrate_from_database()
        self._restore_music_runtime_state_fn()
        self._restore_runtime_state_fn()
        return data

    def migrate_database(self, cfg: DbCfg) -> dict:
        result = ensure_database_and_migrate(cfg)
        if bool(result.get("ok", False)):
            self._db_cfg_setter(cfg)
            self._hydrate_from_database()
        return result
