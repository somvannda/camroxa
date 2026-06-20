"""MusicPageController — owns the Music page UI state and interactions.

Extracted from ``MainWindow`` as part of the *main-window-decomposition* spec
(Requirement 7). The controller owns the music-page event handlers, history
interaction, pool/ngrok controls, and runtime-state persistence glue that used
to live on ``MainWindow`` (the ``_on_music_*`` — excluding ``_on_music_event``
which belongs to ``SignalRouter`` — ``_refresh_music_*``, ``_persist_music_*``,
``_on_music_pool_*``, ``_select_music_history_row`` and music ngrok methods).

The controller does **not** hold a reference to ``MainWindow``. It receives a
small, typed set of collaborators plus a registry of zero-arg accessors:

* ``music_coordinator`` — the :class:`MusicGenerationCoordinator` that performs
  the actual generation / polish / Suno / ngrok work.
* ``db_cfg_accessor`` — returns the live :class:`DbCfg` or ``None`` when the
  database is not configured. All DB-dependent work is skipped when ``None``.
* ``bus`` — the :class:`UiBus` used to emit music events.
* ``settings_accessor`` — returns the merged settings ``dict``.
* ``footer`` — the :class:`FooterController` used for status-bar updates.
* ``widget_accessors`` — maps a name to a zero-arg callable returning the
  corresponding widget, collaborating coordinator, host-state value, or
  host-helper callable. Missing names resolve to ``None`` so the controller
  degrades gracefully without a ``QApplication`` (enabling unit testing).

Accessor keys consumed by this controller (all optional — resolve to ``None``):

  Widgets/state: ``music_draft_title``, ``music_draft_album``,
  ``music_song_lyrics_editor``, ``music_description_editor``,
  ``music_structure_editor``, ``music_settings_profile_list``,
  ``music_history_table``, ``music_history_rows``, ``music_suno_ngrok_status``,
  ``music_data``, ``music_ui_loading``, ``music_suno_auto_poll_enabled``,
  ``window``.

  Collaborators: ``music_settings_coordinator``, ``youtube_coordinator``,
  ``profile_coordinator``, ``music_ngrok_manager``.

  Host-helper callables (bridge methods that still live on the host/mixins
  during the incremental migration): ``log``, ``current_music_song``,
  ``submit_music_song_to_suno``, ``on_music_history_row_selected``,
  ``on_music_open_song_folder_clicked``,
  ``on_music_open_song_channel_folder_clicked``,
  ``refresh_music_ui``, ``refresh_music_history_table``,
  ``refresh_music_profile_lists``, ``refresh_music_match_structure_options``,
  ``refresh_music_saved_text_list``, ``save_music_draft_state``,
  ``persist_music_runtime_state``, ``load_music_settings_profile_details``,
  ``update_music_credit_cost_label``, ``start_suno_credits_refresh_async``,
  ``trigger_music_suno_poll``, ``set_music_current_description``,
  ``set_music_current_structure``, ``set_music_last_batch_only``,
  ``set_music_settings_selected_profile_id``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QListWidgetItem, QMessageBox

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..app.ui_bus import UiBus
    from ..database.persistence import DbCfg
    from .helpers.footer_controller import FooterController
    from ..features.music.coordinator import MusicGenerationCoordinator


class MusicPageController:
    """Owns the Music page event handlers, history, pool, and ngrok controls."""

    def __init__(
        self,
        *,
        music_coordinator: "MusicGenerationCoordinator",
        db_cfg_accessor: Callable[[], "DbCfg | None"],
        bus: "UiBus",
        settings_accessor: Callable[[], dict],
        footer: "FooterController",
        widget_accessors: dict[str, Callable[[], object]],
    ) -> None:
        self._music_coordinator = music_coordinator
        self._db_cfg_accessor = db_cfg_accessor
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._footer = footer
        self._widget_accessors = dict(widget_accessors)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _w(self, name: str) -> object | None:
        """Return the named widget/collaborator/value, or ``None`` if missing."""
        accessor = self._widget_accessors.get(name)
        if accessor is None:
            return None
        try:
            return accessor()
        except Exception:
            return None

    def _invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a host-helper callable resolved via ``widget_accessors``.

        Returns the callable's result, or ``None`` when the helper is missing
        or not callable. Keeps the controller free of a ``MainWindow`` ref.
        """
        fn = self._w(name)
        if callable(fn):
            return fn(*args, **kwargs)
        return None

    def _db_cfg(self) -> "DbCfg | None":
        """Return the live database configuration (may be ``None``)."""
        try:
            return self._db_cfg_accessor()
        except Exception:
            return None

    # -- status / clipboard glue ---------------------------------------
    def _set_music_status(self, text: str) -> None:
        message = str(text or "").strip() or "Ready"
        self._footer.set_music_status(message)
        self._footer.set_status(message)

    def _set_music_suno_status(self, text: str) -> None:
        self._footer.set_suno_status(str(text or "").strip())

    def _set_music_settings_status(self, text: str) -> None:
        message = str(text or "").strip()
        if message:
            self._set_music_status(message)

    def _set_music_pools_status(self, text: str) -> None:
        message = str(text or "").strip()
        if message:
            self._set_music_status(message)

    def _set_music_clipboard(self, text: str, success_message: str) -> None:
        QApplication.clipboard().setText(str(text or ""))
        self._set_music_status(success_message)

    def _trigger_music_suno_poll(self, *, manual: bool = False, max_tasks: int = 10) -> None:
        """Trigger a Suno poll, preserving the host's auto-poll guard."""
        helper = self._w("trigger_music_suno_poll")
        if callable(helper):
            helper(manual=manual, max_tasks=max_tasks)
            return
        if not manual and not bool(self._w("music_suno_auto_poll_enabled")):
            return
        self._music_coordinator.trigger_suno_poll(manual=manual, max_tasks=max_tasks)

    # ------------------------------------------------------------------
    # Generation / polish / Suno
    # ------------------------------------------------------------------
    def on_music_generate_clicked(self) -> None:
        """Handle the Generate button. UI-level entry point that delegates the
        actual generation (and the run/stop toggle) to the coordinator."""
        self._music_coordinator.on_generate_clicked()

    def on_music_polish_clicked(self) -> None:
        """Delegate lyrics polishing to the coordinator."""
        self._music_coordinator.on_polish_clicked()

    def on_music_refresh_suno_clicked(self) -> None:
        """Manually trigger a Suno poll for outstanding tasks."""
        self._trigger_music_suno_poll(manual=True, max_tasks=25)

    def on_music_suno_refresh_credits_clicked(self) -> None:
        """Show a checking status and refresh the Suno credit balance async."""
        self._set_music_suno_status("Checking Suno credits...")
        self._set_music_status("Checking Suno credits...")
        self._invoke("start_suno_credits_refresh_async", force=True)

    def on_music_retry_suno_clicked(self, song: dict | None = None) -> None:
        """Resubmit the selected (or supplied) song to Suno."""
        song = song if isinstance(song, dict) else (self._invoke("current_music_song") or {})
        self._invoke("submit_music_song_to_suno", song, auto=False)

    def on_music_revisions_clicked(self) -> None:
        """Show a summary of the currently selected song's metadata."""
        song = self._invoke("current_music_song") or {}
        title = str(song.get("title", "")).strip() or "No song selected"
        created = str(song.get("createdAt", "")).replace("T", " ")[:16] or "-"
        batch_id = str(song.get("batchId", "")).strip() or "-"
        QMessageBox.information(
            self._w("window"),
            "Revisions",
            f"Title: {title}\nCreated: {created}\nBatch: {batch_id}\n\n"
            "Revision history backend is not ported yet.",
        )

    def on_music_suno_callback_received(self, payload: dict) -> None:
        """React to an inbound Suno callback by emitting a status and polling."""
        self._invoke("log", f"[{time.strftime('%H:%M:%S')}] Suno callback received: {payload}")
        self._bus.music_event.emit({"type": "suno_result", "message": "Suno callback received"})
        self._trigger_music_suno_poll(manual=False, max_tasks=25)

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------
    def on_music_copy_title(self) -> None:
        widget = self._w("music_draft_title")
        text = widget.text() if widget is not None else ""
        self._set_music_clipboard(text, "Copied title")

    def on_music_copy_lyrics(self) -> None:
        widget = self._w("music_song_lyrics_editor")
        text = widget.toPlainText() if widget is not None else ""
        self._set_music_clipboard(text, "Copied lyrics")

    def on_music_copy_both(self) -> None:
        title_widget = self._w("music_draft_title")
        lyrics_widget = self._w("music_song_lyrics_editor")
        title = title_widget.text().strip() if title_widget is not None else ""
        lyrics = lyrics_widget.toPlainText().strip() if lyrics_widget is not None else ""
        payload = f"{title}\n\n{lyrics}".strip()
        self._set_music_clipboard(payload, "Copied title and lyrics")

    # ------------------------------------------------------------------
    # Editor / runtime-state change handlers
    # ------------------------------------------------------------------
    def on_music_description_changed(self) -> None:
        if bool(self._w("music_ui_loading")):
            return
        editor = self._w("music_description_editor")
        if editor is None:
            return
        text = str(editor.toPlainText() or "")
        self._invoke("set_music_current_description", text)
        self._invoke("persist_music_runtime_state")

    def on_music_structure_changed(self) -> None:
        if bool(self._w("music_ui_loading")):
            return
        editor = self._w("music_structure_editor")
        if editor is None:
            return
        text = str(editor.toPlainText() or "")
        self._invoke("set_music_current_structure", text)
        self._invoke("persist_music_runtime_state")

    def on_music_draft_changed(self) -> None:
        if bool(self._w("music_ui_loading")):
            return
        data = self._w("music_data")
        if not isinstance(data, dict):
            return
        drafts = data.get("songDrafts") if isinstance(data.get("songDrafts"), list) else []
        if not drafts:
            drafts = [{"id": "draft-01", "title": "", "album": ""}]
            data["songDrafts"] = drafts
        title_widget = self._w("music_draft_title")
        album_widget = self._w("music_draft_album")
        drafts[0]["title"] = str(title_widget.text() or "").strip() if title_widget is not None else ""
        drafts[0]["album"] = str(album_widget.text() or "").strip() if album_widget is not None else ""
        self._invoke("save_music_draft_state")

    def on_music_last_batch_changed(self, checked: bool) -> None:
        if bool(self._w("music_ui_loading")):
            return
        self._invoke("set_music_last_batch_only", bool(checked))
        self._invoke("persist_music_runtime_state")
        self._invoke("refresh_music_history_table")

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    def on_music_profile_item_clicked(self, kind: str, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        if not bool(item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        current = item.checkState()
        item.setCheckState(
            Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
        )

    def on_music_settings_profile_selected(self) -> None:
        widget = self._w("music_settings_profile_list")
        item = widget.currentItem() if widget is not None else None
        profile_id = (
            str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item is not None else None
        )
        self._invoke("set_music_settings_selected_profile_id", profile_id)
        self._invoke("load_music_settings_profile_details")

    def on_music_profile_youtube_connect(self) -> None:
        coordinator = self._w("youtube_coordinator")
        if coordinator is not None:
            return coordinator.connect_profile()
        return None

    def on_music_profile_youtube_disconnect(self) -> None:
        coordinator = self._w("youtube_coordinator")
        if coordinator is not None:
            return coordinator.disconnect_profile()
        return None

    # ------------------------------------------------------------------
    # ngrok controls
    # ------------------------------------------------------------------
    def on_music_ngrok_start(self) -> None:
        self._music_coordinator.on_ngrok_start()

    def on_music_ngrok_stop(self) -> None:
        self._music_coordinator.on_ngrok_stop()

    def on_music_ngrok_refresh(self) -> None:
        self.refresh_music_ngrok_status()

    def refresh_music_ngrok_status(self) -> None:
        label = self._w("music_suno_ngrok_status")
        if label is None:
            return
        manager = self._w("music_ngrok_manager")
        if manager is None:
            return
        status = manager.status()
        if status.get("running"):
            url = str(status.get("callbackUrl") or status.get("publicUrl") or "(starting...)").strip()
            text = f"Running: {url}"
        else:
            last_error = str(status.get("lastError", "")).strip()
            text = f"Not running{f' · {last_error}' if last_error else ''}"
        label.setText(text)

    # ------------------------------------------------------------------
    # Database / pool management (delegated to MusicSettingsCoordinator)
    # ------------------------------------------------------------------
    def on_music_test_db_clicked(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_test_db_clicked()
        return None

    def on_music_migrate_db_clicked(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_migrate_db_clicked()
        return None

    def refresh_music_pool_stats(self, force: bool = False) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.refresh_music_pool_stats(force=force)
        return None

    def refresh_music_pool_table(self, force: bool = False) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.refresh_music_pool_table(force=force)
        return None

    def refresh_music_pool_preview(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.refresh_music_pool_preview()
        return None

    def on_music_pool_row_selected(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_row_selected()
        return None

    def on_music_pool_kind_changed(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_kind_changed()
        return None

    def on_music_pool_prev_page(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_prev_page()
        return None

    def on_music_pool_next_page(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_next_page()
        return None

    def on_music_pool_generate(self) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_generate()
        return None

    def on_music_pool_import(self, kind: str | None = None) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_import(kind)
        return None

    def on_music_pool_clear(self, kind: str | None = None) -> None:
        coordinator = self._w("music_settings_coordinator")
        if coordinator is not None:
            return coordinator.on_music_pool_clear(kind)
        return None

    def on_music_clear_generated_clicked(self) -> None:
        parent = self._w("window")
        confirm = QMessageBox.question(
            parent,
            "Database",
            "Delete ALL generated songs from Postgres (songs + history)?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        ok, message = self._music_coordinator.clear_generated()
        if ok:
            self._invoke("refresh_music_ui")
            self._set_music_pools_status(message)
        else:
            QMessageBox.warning(parent, "Database", message)

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------
    def refresh_music_settings_profile_list(self) -> None:
        coordinator = self._w("profile_coordinator")
        if coordinator is not None:
            return coordinator.refresh_list()
        return None

    def refresh_music_settings_profile_youtube_playlists(self, profile_id: str, selected_id: str) -> None:
        coordinator = self._w("youtube_coordinator")
        if coordinator is not None:
            coordinator.refresh_profile_playlists(profile_id, selected_id)

    def refresh_music_reference_views(self) -> None:
        self._invoke("refresh_music_profile_lists")
        self.refresh_music_settings_profile_list()
        self._invoke("refresh_music_match_structure_options")
        self._invoke("refresh_music_saved_text_list", "descriptions")
        self._invoke("refresh_music_saved_text_list", "structures")
        self.refresh_music_ngrok_status()
        self.refresh_music_pool_stats()
        self.refresh_music_pool_table()
        self._invoke("refresh_music_history_table")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def persist_music_date_filters(self, source: str = "run") -> None:
        self._music_coordinator.persist_date_filters(source)
        self._invoke("update_music_credit_cost_label")

    # ------------------------------------------------------------------
    # History interaction
    # ------------------------------------------------------------------
    def select_music_history_row(self, row_index: int) -> None:
        table = self._w("music_history_table")
        if table is None:
            return
        rows = self._w("music_history_rows")
        rows = rows if isinstance(rows, list) else []
        if row_index < 0 or row_index >= len(rows):
            return
        table.setCurrentCell(row_index, 0)
        table.selectRow(row_index)
        self._invoke("on_music_history_row_selected")

    def on_music_history_retry_suno_clicked(self, row_index: int, song: dict) -> None:
        self.select_music_history_row(row_index)
        self.on_music_retry_suno_clicked(song)

    def on_music_history_open_folder_clicked(self, row_index: int, song: dict) -> None:
        self.select_music_history_row(row_index)
        self._invoke("on_music_open_song_folder_clicked", song)

    def on_music_history_open_ok_folder_clicked(self, row_index: int, song: dict) -> None:
        self.select_music_history_row(row_index)
        self._invoke("on_music_open_song_channel_folder_clicked", song, channel="ok")

    def on_music_history_open_alt_folder_clicked(self, row_index: int, song: dict) -> None:
        self.select_music_history_row(row_index)
        self._invoke("on_music_open_song_channel_folder_clicked", song, channel="alt")

    def on_music_hide_batch_done(self, worker: object, batch_id: str, progress: QLabel) -> None:
        progress.close()
        error = getattr(worker, "error", None)
        if error:
            QMessageBox.warning(
                self._w("window"), "Hide Batch", f"Failed to hide batch {batch_id}: {error}"
            )
            return
        result = getattr(worker, "result", None) or {}
        count = result.get("hidden_count", 0)
        self._invoke("refresh_music_history_table", force=True)
        self._set_music_status(f"Hidden batch {batch_id}: {count} songs removed")
