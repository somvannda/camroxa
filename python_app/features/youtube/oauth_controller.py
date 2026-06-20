"""
YouTubeOAuthController — OAuth app CRUD, profile connect/disconnect, uploads.

Owns the YouTube OAuth-app management surface previously embedded in
``MainWindow``: the OAuth apps table, the editor form, profile connection and
disconnection, OAuth client resolution, and upload enqueueing. Client secrets
are encrypted with DPAPI (``dpapi_encrypt_to_base64``) before persistence and
decrypted (``dpapi_decrypt_from_base64``) when loaded for display.

The controller does NOT hold a reference to ``MainWindow``. It receives:

* ``db_cfg_accessor`` — returns the current ``DbCfg`` or ``None``.
* ``youtube_coordinator`` — the existing ``YouTubeCoordinator`` it delegates to.
* ``settings_accessor`` — returns the current music settings dict.
* ``widget_accessors`` — a mapping of name -> zero-arg callable returning a
  widget (or a bound helper callable). Missing entries resolve to ``None`` so
  the controller is constructable and testable without a ``QApplication``.
* ``persist_fn`` — optional callback for persisting a settings patch.

When ``db_cfg_accessor()`` returns ``None`` every database operation is skipped
gracefully without raising.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..ports import ConfirmQuestionFn, TablePopulateFn, WarningFn
from ...models.music_model import create_id
from ...services.dpapi import dpapi_decrypt_from_base64, dpapi_encrypt_to_base64
from .db import (
    YouTubeOAuthApp,
    db_count_profiles_using_youtube_oauth_app,
    db_delete_youtube_oauth_app,
    db_get_youtube_oauth_app,
    db_list_youtube_oauth_apps,
    db_upsert_youtube_oauth_app,
)

if TYPE_CHECKING:
    from ...database.persistence import DbCfg
    from .coordinator import YouTubeCoordinator


class YouTubeOAuthController:
    """Owns YouTube OAuth-app CRUD, profile connection, and upload enqueueing.

    All widget interaction flows through ``widget_accessors`` so the controller
    can be instantiated with plain callables (or lambdas returning mocks) in a
    test without a Qt application or a live ``MainWindow``.
    """

    def __init__(
        self,
        *,
        db_cfg_accessor: Callable[[], "DbCfg | None"],
        youtube_coordinator: "YouTubeCoordinator",
        settings_accessor: Callable[[], dict],
        widget_accessors: dict[str, Callable[[], object]],
        persist_fn: Callable[[dict], None] | None = None,
        warning_fn: WarningFn | None = None,
        confirm_question_fn: ConfirmQuestionFn | None = None,
        table_populate_fn: TablePopulateFn | None = None,
    ) -> None:
        """Store injected dependencies and initialise controller-owned state.

        Parameters
        ----------
        db_cfg_accessor:
            Returns the active ``DbCfg`` or ``None`` when the database is not
            configured. Every DB operation is skipped when this returns ``None``.
        youtube_coordinator:
            The ``YouTubeCoordinator`` that owns connect/disconnect, OAuth flow,
            upload enqueueing, and merged-output scanning.
        settings_accessor:
            Returns the current music settings dict (used to fall back to the
            global YouTube client id/secret when a profile has no OAuth app).
        widget_accessors:
            Mapping of name -> zero-arg callable returning a widget or bound
            helper. Missing entries resolve to ``None`` via :meth:`_widget`.
        persist_fn:
            Optional callback invoked with a settings patch dict to persist a
            change. Currently reserved for future use; may be ``None``.
        warning_fn:
            Optional callable for displaying warning dialogs. Signature:
            ``(title, message) -> None``. No-op when ``None``.
        confirm_question_fn:
            Optional callable for yes/no confirmation dialogs. Signature:
            ``(title, message) -> bool``. Returns ``False`` when ``None``.
        table_populate_fn:
            Optional callable for populating the OAuth apps table. Signature:
            ``(rows: list[list[tuple[int, str, str]]]) -> None``. No-op when ``None``.
        """
        self._db_cfg_accessor = db_cfg_accessor
        self._youtube_coordinator = youtube_coordinator
        self._settings_accessor = settings_accessor
        self._widget_accessors: dict[str, Callable[[], object]] = dict(widget_accessors or {})
        self._persist_fn = persist_fn
        self._warning_fn: WarningFn = warning_fn or (lambda _title, _msg: None)
        self._confirm_question_fn: ConfirmQuestionFn = confirm_question_fn or (lambda _title, _msg: False)
        self._table_populate_fn: TablePopulateFn = table_populate_fn or (lambda _rows: None)

        # Controller-owned state (previously stored on MainWindow).
        self._youtube_oauth_apps_cache: list[YouTubeOAuthApp] = []
        self._youtube_oauth_app_edit_id: str = ""

    # ------------------------------------------------------------------
    # Safe accessor helpers
    # ------------------------------------------------------------------

    def _widget(self, name: str) -> Any | None:
        """Return the widget/helper for *name*, or ``None`` when unavailable.

        Never raises: a missing key or a failing accessor both resolve to
        ``None`` so call sites can guard with a simple ``is not None`` check.
        """
        accessor = self._widget_accessors.get(name)
        if accessor is None:
            return None
        try:
            return accessor()
        except Exception:
            return None

    def _invoke(self, name: str, *args: Any, **kwargs: Any) -> Any | None:
        """Call the helper callable registered under *name* if present.

        Returns the callable's result, or ``None`` when the accessor is missing
        or does not resolve to a callable.
        """
        fn = self._widget(name)
        if callable(fn):
            return fn(*args, **kwargs)
        return None

    def _db_cfg(self) -> "DbCfg | None":
        """Return the current database configuration (may be ``None``)."""
        return self._db_cfg_accessor()

    def _music_settings(self) -> dict:
        """Return the current music settings dict via the injected accessor."""
        settings = self._settings_accessor()
        return settings if isinstance(settings, dict) else {}

    def _music_profile_by_id(self, profile_id: str) -> dict | None:
        """Look up a music profile by id via the injected helper accessor."""
        result = self._invoke("music_profile_by_id", profile_id)
        return result if isinstance(result, dict) else None

    def _log(self, msg: str) -> None:
        """Forward a log line via the injected ``log`` helper if present."""
        self._invoke("log", msg)

    def _set_music_status(self, text: str) -> None:
        """Forward a status message via the injected ``set_music_status`` helper."""
        self._invoke("set_music_status", text)

    def _load_music_settings_profile_details(self) -> None:
        """Reload profile details via the injected helper if present."""
        self._invoke("load_music_settings_profile_details")

    def _current_primary_page(self) -> str:
        """Return the current primary page key (empty string when unknown)."""
        page = self._widget("current_primary_page")
        return str(page or "")

    def _dialog_parent(self) -> Any | None:
        """Return the parent widget to use for modal dialogs (may be ``None``)."""
        return self._widget("dialog_parent")

    @staticmethod
    def _time_now() -> str:
        """Return the current wall-clock time formatted as ``HH:MM:SS``."""
        return time.strftime("%H:%M:%S")

    @staticmethod
    def _mask_client_id(text: str) -> str:
        """Return a masked rendering of a client id for table display."""
        s = str(text or "").strip()
        if not s:
            return ""
        if len(s) <= 14:
            return s
        return f"{s[:6]}…{s[-6:]}"

    def _profiles_tab_active(self) -> bool:
        """Return ``True`` when the settings page is showing the Profiles tab."""
        if self._current_primary_page() != "settings":
            return False
        tabs = self._widget("music_settings_tabs")
        if tabs is None:
            return False
        try:
            return str(tabs.tabText(tabs.currentIndex()) or "").strip().lower() == "profiles"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # OAuth apps table + editor
    # ------------------------------------------------------------------

    def refresh_youtube_oauth_apps_table(self, *, selected_id: str = "") -> None:
        """Reload the OAuth apps table from the database.

        Skips the query (and clears the table) when no database is configured.
        Optionally re-selects the row whose OAuth app id equals *selected_id*.
        """
        table = self._widget("youtube_oauth_apps_table")
        if table is None:
            return
        table.blockSignals(True)
        table.setRowCount(0)
        db_cfg = self._db_cfg()
        if not db_cfg:
            self._log(f"[{self._time_now()}] YouTube OAuth list skipped: db_cfg is None")
            table.blockSignals(False)
            return
        try:
            apps = db_list_youtube_oauth_apps(db_cfg, limit=500)
            self._log(f"[{self._time_now()}] YouTube OAuth apps loaded: {len(apps)}")
        except Exception as exc:
            self._log(f"[{self._time_now()}] YouTube OAuth list failed: {exc}")
            apps = []
        self._youtube_oauth_apps_cache = apps

        # Build rows for the table populate callable.
        # Each row is a list of (column_index, display_text, user_role_data) tuples.
        rows: list[list[tuple[int, str, str]]] = []
        for app in apps:
            rows.append([
                (0, str(app.name or ""), str(app.id or "")),
                (1, self._mask_client_id(str(app.client_id or "")), ""),
                (2, str(app.updated_at or ""), ""),
            ])
        self._table_populate_fn(rows)

        table.blockSignals(False)
        if selected_id:
            for i, app in enumerate(self._youtube_oauth_apps_cache):
                if str(app.id or "").strip() == str(selected_id or "").strip():
                    table.setCurrentCell(i, 0)
                    break

    def on_youtube_oauth_app_selected(self, row_index: int) -> None:
        """Load the selected OAuth app into the editor, decrypting its secret."""
        db_cfg = self._db_cfg()
        if not db_cfg:
            return
        table = self._widget("youtube_oauth_apps_table")
        if table is None:
            return
        if row_index < 0 or row_index >= int(table.rowCount()):
            return
        # Resolve the OAuth app id from the cache rather than reading Qt item data.
        if row_index >= len(self._youtube_oauth_apps_cache):
            return
        oauth_id = str(self._youtube_oauth_apps_cache[row_index].id or "").strip()
        if not oauth_id:
            return
        try:
            app = db_get_youtube_oauth_app(db_cfg, oauth_id)
            if app is None:
                raise RuntimeError("OAuth app not found")
            secret = dpapi_decrypt_from_base64(str(app.client_secret_enc or ""))
            self._youtube_oauth_app_edit_id = str(app.id or "")
            name_widget = self._widget("youtube_oauth_app_name")
            if name_widget is not None:
                name_widget.setText(str(app.name or ""))
            client_id_widget = self._widget("youtube_oauth_app_client_id")
            if client_id_widget is not None:
                client_id_widget.setText(str(app.client_id or ""))
            secret_widget = self._widget("youtube_oauth_app_client_secret")
            if secret_widget is not None:
                secret_widget.setText(str(secret or ""))
        except Exception as exc:
            self._set_music_status(f"YouTube OAuth app load failed: {exc}")

    def new_youtube_oauth_app(self) -> None:
        """Reset the editor to create a brand-new OAuth app entry."""
        self._youtube_oauth_app_edit_id = create_id("ytapp")
        table = self._widget("youtube_oauth_apps_table")
        if table is not None:
            table.clearSelection()
        name_widget = self._widget("youtube_oauth_app_name")
        if name_widget is not None:
            name_widget.setText("")
        client_id_widget = self._widget("youtube_oauth_app_client_id")
        if client_id_widget is not None:
            client_id_widget.setText("")
        secret_widget = self._widget("youtube_oauth_app_client_secret")
        if secret_widget is not None:
            secret_widget.setText("")

    def save_youtube_oauth_app(self) -> None:
        """Validate the editor, encrypt the secret, and persist the OAuth app."""
        db_cfg = self._db_cfg()
        if not db_cfg:
            self._warning_fn("YouTube", "Database is not configured.")
            return
        oid = str(self._youtube_oauth_app_edit_id or "").strip()
        if not oid:
            oid = create_id("ytapp")
            self._youtube_oauth_app_edit_id = oid
        name_widget = self._widget("youtube_oauth_app_name")
        client_id_widget = self._widget("youtube_oauth_app_client_id")
        secret_widget = self._widget("youtube_oauth_app_client_secret")
        name = str(name_widget.text() or "").strip() if name_widget is not None else ""
        client_id = str(client_id_widget.text() or "").strip() if client_id_widget is not None else ""
        secret = str(secret_widget.text() or "").strip() if secret_widget is not None else ""
        if not name or not client_id or not secret:
            self._warning_fn("YouTube", "Name, Client ID, and Client Secret are required.")
            return
        try:
            enc = dpapi_encrypt_to_base64(secret)
            saved = db_upsert_youtube_oauth_app(db_cfg, {"id": oid, "name": name, "clientId": client_id, "clientSecretEnc": enc})
            if not saved:
                raise RuntimeError("Save failed")
        except Exception as exc:
            self._warning_fn("YouTube", f"Save failed: {exc}")
            return
        self.refresh_youtube_oauth_apps_table(selected_id=oid)
        if self._profiles_tab_active():
            self._load_music_settings_profile_details()
        self._set_music_status("YouTube OAuth app saved")

    def delete_youtube_oauth_app(self) -> None:
        """Delete the selected OAuth app after confirming it is unused."""
        db_cfg = self._db_cfg()
        if not db_cfg:
            self._warning_fn("YouTube", "Database is not configured.")
            return
        oid = str(self._youtube_oauth_app_edit_id or "").strip()
        if not oid:
            self._warning_fn("YouTube", "Select an OAuth app first.")
            return
        try:
            used = db_count_profiles_using_youtube_oauth_app(db_cfg, oid)
            if used > 0:
                self._warning_fn("YouTube", f"Cannot delete. This OAuth app is used by {used} profile(s).")
                return
            if not self._confirm_question_fn("YouTube", "Delete this OAuth app?"):
                return
            db_delete_youtube_oauth_app(db_cfg, oid)
        except Exception as exc:
            self._warning_fn("YouTube", f"Delete failed: {exc}")
            return
        self._youtube_oauth_app_edit_id = ""
        self.new_youtube_oauth_app()
        self.refresh_youtube_oauth_apps_table()
        if self._profiles_tab_active():
            self._load_music_settings_profile_details()
        self._set_music_status("YouTube OAuth app deleted")

    # ------------------------------------------------------------------
    # OAuth client resolution
    # ------------------------------------------------------------------

    def resolve_youtube_oauth_client(self, profile_id: str) -> tuple[str, str]:
        """Return ``(client_id, client_secret)`` for a profile.

        Prefers the profile's selected OAuth app (decrypting its stored secret);
        falls back to the global YouTube client id/secret from settings. Raises
        ``RuntimeError`` when no usable credentials can be resolved.
        """
        pid = str(profile_id or "").strip()
        profile = self._music_profile_by_id(pid) or {}
        oauth_app_id = str(profile.get("youtubeOauthAppId", "")).strip()
        if oauth_app_id:
            db_cfg = self._db_cfg()
            if not db_cfg:
                raise RuntimeError("Database is not configured")
            app = db_get_youtube_oauth_app(db_cfg, oauth_app_id)
            if app is None:
                raise RuntimeError(f"Selected YouTube OAuth app is missing: {oauth_app_id}")
            cid = str(app.client_id or "").strip()
            sec = dpapi_decrypt_from_base64(str(app.client_secret_enc or ""))
            if not cid or not sec:
                raise RuntimeError("Selected YouTube OAuth app is incomplete")
            return (cid, sec)
        settings = self._music_settings()
        cid = str(settings.get("youtubeClientId", "")).strip()
        sec = str(settings.get("youtubeClientSecret", "")).strip()
        if not cid or not sec:
            raise RuntimeError("YouTube OAuth client id/secret is missing. Set it in Settings → API or select an OAuth app in the profile.")
        return (cid, sec)

    # ------------------------------------------------------------------
    # Profile connect / disconnect + uploads (delegated to coordinator)
    # ------------------------------------------------------------------

    def youtube_connect_cancel_event_for(self, profile_id: str) -> Any:
        """Return (or create) the connect-cancellation event for *profile_id*."""
        return self._youtube_coordinator.connect_cancel_event_for(profile_id)

    def clear_youtube_connect_state(self, profile_id: str) -> None:
        """Clear any in-progress connect UI state for *profile_id*."""
        return self._youtube_coordinator.clear_connect_state(profile_id)

    def on_music_profile_youtube_connect(self) -> None:
        """Start connecting the selected profile's YouTube account."""
        return self._youtube_coordinator.connect_profile()

    def on_music_profile_youtube_disconnect(self) -> None:
        """Disconnect the selected profile's YouTube account."""
        return self._youtube_coordinator.disconnect_profile()

    def start_youtube_oauth_connect(self, profile_id: str, *, client_id: str, client_secret: str) -> None:
        """Begin the OAuth connect flow for *profile_id* with given credentials."""
        return self._youtube_coordinator.start_oauth_connect(
            profile_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    def enqueue_youtube_upload_for_merge(self, *, batch_id: str, profile_id: str, role: str, merged_mp4_path: str) -> None:
        """Enqueue a YouTube upload job for a freshly merged MP4 output."""
        return self._youtube_coordinator.enqueue_upload_for_merge(
            batch_id=batch_id,
            profile_id=profile_id,
            role=role,
            merged_mp4_path=merged_mp4_path,
        )

    def youtube_scan_for_merged_outputs(self) -> None:
        """Scan for merged outputs and enqueue auto-uploads as configured."""
        return self._youtube_coordinator.scan_for_merged_outputs()
