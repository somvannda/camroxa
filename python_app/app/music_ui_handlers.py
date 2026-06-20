"""Auto-extracted UI handler methods from MainWindow."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize, QThread, QDate, QTimer
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMenu, QListWidgetItem, QTableWidgetItem,
    QWidget, QHBoxLayout, QPushButton, QSizePolicy, QComboBox,
    QListWidget, QMessageBox, QHeaderView, QTableWidget,
)

from ..views.helpers import widget_factory
from ..views.helpers.style_helper import apply_cta_button, render_svg_icon
from PyQt6.QtGui import QAction, QColor

from ..database.music_db import (
    get_latest_suno_output_dirs_by_song_uid,
    list_latest_suno_tasks_by_song_uids,
    list_songs_for_history,
    remap_pending_suno_output_dirs,
    upsert_song as music_upsert_song,
)
from ..database.persistence import DbCfg, db_list_video_templates, read_local_templates, write_local_templates
from ..models.music_model import default_music_app_data, next_saved_text_name, now_iso
from ..services.music_generation import opening2 as music_opening2


from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox,
    QFileDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton,
    QSlider, QToolButton, QWidget,
)
from ..models.music_model import normalize_music_app_data
import os
import random

class MusicUiHandlersMixin:
    """Mixin providing UI interaction handlers extracted from MainWindow."""

    def _music_date_list(self) -> list[str]:
        start = self._parse_music_date_ymd(self.music_run_from_date)
        end = self._parse_music_date_ymd(self.music_run_to_date)
        if start is None or end is None:
            raise ValueError("Invalid date range")
        if start > end:
            raise ValueError("From date must be before To date")
        out: list[str] = []
        current = QDate(start)
        while current <= end:
            out.append(current.toString("yyyy-MM-dd"))
            current = current.addDays(1)
        return out

    def _music_recent_uniqueness_lists(self, limit: int) -> dict[str, list[str]]:
        songs = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
        rows = [dict(song) for song in songs if isinstance(song, dict)]
        rows.sort(key=lambda x: str(x.get("createdAt", "")), reverse=True)
        rows = rows[: max(1, min(5000, int(limit or 100)))]
        return {
            "titles": [str(row.get("title", "")).strip() for row in rows if str(row.get("title", "")).strip()],
            "albums": [str(row.get("album", "")).strip() for row in rows if str(row.get("album", "")).strip()],
            "openings": [
                music_opening2(str(row.get("lyricsPolished", "") or row.get("lyricsRaw", ""))).strip()
                for row in rows
                if music_opening2(str(row.get("lyricsPolished", "") or row.get("lyricsRaw", ""))).strip()
            ],
        }

    def _persist_music_runtime_state(self):
        self._persist_setting_patch(
            {
                "musicCurrentDescription": self.music_current_description,
                "musicCurrentStructure": self.music_current_structure,
                "musicCurrentSongId": self.music_current_song_id or "",
                "musicRunFromDate": self.music_run_from_date,
                "musicRunToDate": self.music_run_to_date,
                "musicHistoryFromDate": getattr(self, "music_history_from_date", ""),
                "musicHistoryToDate": getattr(self, "music_history_to_date", ""),
                "musicLastBatchOnly": bool(self.music_last_batch_only),
            }
        )

    def _restore_music_runtime_state(self):
        s = self.e_settings or {}
        self.music_current_description = str(s.get("musicCurrentDescription", "")).strip()
        self.music_current_structure = str(s.get("musicCurrentStructure", "")).strip()
        current_song = str(s.get("musicCurrentSongId", "")).strip()
        self.music_current_song_id = current_song or None
        self.music_run_from_date = str(s.get("musicRunFromDate", "")).strip()
        self.music_run_to_date = str(s.get("musicRunToDate", "")).strip()
        self.music_history_from_date = str(s.get("musicHistoryFromDate", "")).strip()
        self.music_history_to_date = str(s.get("musicHistoryToDate", "")).strip()
        self.music_last_batch_only = bool(s.get("musicLastBatchOnly", False)) if "musicLastBatchOnly" in s else False
        if not self.music_current_description:
            descriptions = self.music_data.get("descriptions") or []
            if descriptions:
                self.music_current_description = str((descriptions[0] or {}).get("content", "")).strip()
        if not self.music_current_structure:
            structures = self.music_data.get("structures") or []
            if structures:
                self.music_current_structure = str((structures[0] or {}).get("content", "")).strip()

    def _refresh_music_match_structure_options(self):
        combo = getattr(self, "music_descriptions_match_key", None)
        if combo is None:
            return
        current_value = str(combo.currentData() or combo.currentText() or "").strip()
        structures = self._music_collection("structures")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(no match)", userData="")
        for row in structures:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip() or "Untitled"
            combo.addItem(name, userData=name)
        idx = combo.findData(current_value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_music_profile_lists(self):
        settings = self._music_settings()
        data = self._music_coordinator.load_profiles()
        profiles = data["profiles"]
        ok_selected_list = data["ok_selected_list"]
        alt_selected_list = data["alt_selected_list"]
        ok_selected = {str(x).strip() for x in ok_selected_list if str(x).strip()}
        alt_selected = {str(x).strip() for x in alt_selected_list if str(x).strip()}
        bundles = [
            ("ok", getattr(self, "music_ok_profiles", None), ok_selected_list, alt_selected),
            ("alt", getattr(self, "music_alt_profiles", None), alt_selected_list, ok_selected),
        ]
        for _, widget, selected_ids, blocked_ids in bundles:
            if widget is None:
                continue
            widget.blockSignals(True)
            widget.clear()
            for profile in profiles:
                profile_id = str((profile or {}).get("id", "")).strip()
                base_name = str((profile or {}).get("name", "Unnamed Profile"))
                
                checked = profile_id in selected_ids
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, profile_id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                
                is_disabled = profile_id in blocked_ids and not checked
                if is_disabled:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                
                widget.addItem(item)
                
                row_widget = QWidget()
                row_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(4, 0, 8, 0)
                
                name_label = QLabel(base_name)
                name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                if is_disabled:
                    name_label.setStyleSheet(f"color: {self.ui['text_muted']};")
                else:
                    name_label.setStyleSheet("color: #f3f7ff;")
                row_layout.addWidget(name_label)
                row_layout.addStretch()
                
                if checked:
                    try:
                        idx = selected_ids.index(profile_id)
                        num_label = QLabel(str(idx))
                        num_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                        self._set_label_role(num_label, "meta")
                        row_layout.addWidget(num_label)
                    except ValueError:
                        pass
                
                from PyQt6.QtCore import QSize
                item.setSizeHint(QSize(0, 26))
                widget.setItemWidget(item, row_widget)
            widget.blockSignals(False)
        if hasattr(self, "music_ok_count_label"):
            self.music_ok_count_label.setText(str(len(ok_selected_list)))
        if hasattr(self, "music_alt_count_label"):
            self.music_alt_count_label.setText(str(len(alt_selected_list)))

    def _on_music_profile_item_changed(self, kind: str):
        if self._music_ui_loading:
            return
        widget = self.music_ok_profiles if str(kind) == "ok" else self.music_alt_profiles
        settings = self._music_settings()
        current_key = "channelOkProfileIds" if str(kind) == "ok" else "channelAltProfileIds"
        current_ids = list(settings.get(current_key) or [])
        
        checked_set = set()
        for i in range(widget.count()):
            item = widget.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                profile_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
                if profile_id:
                    checked_set.add(profile_id)
        
        # Build new ordered list: keep existing order, append new ones, remove unchecked ones
        new_ids = [x for x in current_ids if x in checked_set]
        for x in checked_set:
            if x not in new_ids:
                new_ids.append(x)
                
        other_key = "channelAltProfileIds" if str(kind) == "ok" else "channelOkProfileIds"
        other_ids = [x for x in list(settings.get(other_key) or []) if str(x).strip() and str(x).strip() not in checked_set]
        
        patch = {"channelOkProfileIds": new_ids, "channelAltProfileIds": other_ids} if str(kind) == "ok" else {"channelAltProfileIds": new_ids, "channelOkProfileIds": other_ids}
        if str(kind) == "ok":
            patch["activeProfileId"] = new_ids[0] if new_ids else None
            patch["activeProfileOkId"] = new_ids[0] if new_ids else None
            patch["activeProfileAltId"] = other_ids[0] if other_ids else None
        else:
            patch["activeProfileOkId"] = other_ids[0] if other_ids else None
            patch["activeProfileAltId"] = new_ids[0] if new_ids else None
        self._update_music_settings(patch)
        self._music_ui_loading = True
        try:
            self._refresh_music_profile_lists()
        finally:
            self._music_ui_loading = False

    def _refresh_music_saved_text_list(self, kind: str):
        widget, _, _, _ = self._music_text_widget_bundle(kind)
        if widget is None:
            return
        data = self._music_coordinator.load_saved_texts(kind)
        rows = data["rows"]
        active_ids = set(data["active_ids"])
        current_id = ""
        if isinstance(widget, QListWidget):
            current_item = widget.currentItem()
            if current_item is not None:
                current_id = str(current_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        elif isinstance(widget, QTableWidget):
            current_item = widget.currentItem()
            if current_item is not None:
                current_id = str(current_item.data(Qt.ItemDataRole.UserRole) or "").strip()
        widget.blockSignals(True)
        if isinstance(widget, QListWidget):
            widget.clear()
            selected_idx = -1
            for row_idx, row in enumerate(rows):
                row_id = str((row or {}).get("id", "")).strip()
                name = str((row or {}).get("name", "Untitled")).strip() or "Untitled"
                suffix = "  [Active]" if row_id in active_ids else ""
                item = QListWidgetItem(f"{row_idx + 1}. {name}{suffix}")
                item.setData(Qt.ItemDataRole.UserRole, row_id)
                if row_id in active_ids:
                    item.setForeground(QColor("#dff6ea"))
                widget.addItem(item)
                if row_id and row_id == current_id:
                    selected_idx = row_idx
            if selected_idx >= 0:
                widget.setCurrentRow(selected_idx)
            elif rows:
                widget.setCurrentRow(0)
        elif isinstance(widget, QTableWidget):
            widget.clearContents()
            widget.setRowCount(len(rows))
            widget.setColumnCount(4)
            widget.setHorizontalHeaderLabels(["No", "Name", "Status", "Date Created"])
            widget.horizontalHeader().setStretchLastSection(False)
            widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            selected_idx = -1
            for row_idx, row in enumerate(rows):
                row_id = str((row or {}).get("id", "")).strip()
                name = str((row or {}).get("name", "Untitled")).strip() or "Untitled"
                status = "Active" if row_id in active_ids else "Saved"
                created_at = str((row or {}).get("createdAt", "")).strip() or str((row or {}).get("updatedAt", "")).strip()
                values = [
                    str(row_idx + 1),
                    name,
                    status,
                    widget_factory.format_music_updated_at(created_at),
                ]
                for col_idx, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, row_id)
                    if col_idx == 2 and status == "Active":
                        item.setForeground(QColor("#dff6ea"))
                    widget.setItem(row_idx, col_idx, item)
                if row_id and row_id == current_id:
                    selected_idx = row_idx
            if selected_idx >= 0:
                widget.setCurrentCell(selected_idx, 0)
            elif rows:
                widget.setCurrentCell(0, 0)
        widget.blockSignals(False)

    def _on_music_saved_text_selected(self, kind: str, row_index: int):
        widget, name_edit, match_edit, editor = self._music_text_widget_bundle(kind)
        rows = self._music_collection(kind)
        if widget is None or name_edit is None or editor is None:
            return
        if row_index < 0 or row_index >= len(rows):
            name_edit.setText("")
            if match_edit is not None:
                if isinstance(match_edit, QComboBox):
                    match_edit.setCurrentIndex(0)
                else:
                    match_edit.setText("")
            editor.setPlainText("")
            return
        row = rows[row_index] if isinstance(rows[row_index], dict) else {}
        name_edit.setText(str(row.get("name", "")).strip())
        if match_edit is not None:
            match_value = str(row.get("matchKey", "")).strip()
            if isinstance(match_edit, QComboBox):
                idx = match_edit.findData(match_value)
                match_edit.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                match_edit.setText(match_value)
        editor.setPlainText(str(row.get("content", "") or row.get("text", "")))

    def _new_music_saved_text(self, kind: str):
        widget, name_edit, match_edit, editor = self._music_text_widget_bundle(kind)
        if widget is not None:
            widget.clearSelection()
            if isinstance(widget, QListWidget):
                widget.setCurrentRow(-1)
            elif hasattr(widget, "setCurrentCell"):
                widget.setCurrentCell(-1, -1)
        if name_edit is not None:
            name_edit.setText(next_saved_text_name(self._music_collection(kind)))
        if match_edit is not None:
            if isinstance(match_edit, QComboBox):
                match_edit.setCurrentIndex(0)
            else:
                match_edit.setText("")
        if editor is not None:
            editor.setPlainText("")

    def _save_music_saved_text(self, kind: str):
        widget, name_edit, match_edit, editor = self._music_text_widget_bundle(kind)
        if name_edit is None or editor is None:
            return
        rows = list(self._music_collection(kind))
        name = str(name_edit.text() or "").strip() or next_saved_text_name(rows)
        content = str(editor.toPlainText() or "").strip()
        if not content:
            QMessageBox.warning(self, "Save Text", "Content cannot be empty.")
            return
        
        selected_row = widget.currentRow() if isinstance(widget, QListWidget) else (widget.currentRow() if widget else -1)
        existing_id = ""
        existing_created_at = ""
        if 0 <= selected_row < len(rows):
            current_row = rows[selected_row] or {}
            existing_id = str(current_row.get("id", "")).strip()
            existing_created_at = str(current_row.get("createdAt", "")).strip()
        
        match_key = (
            str(match_edit.currentData() or "").strip()
            if isinstance(match_edit, QComboBox)
            else str(match_edit.text() or "").strip()
        ) if match_edit is not None else ""

        item, updated_rows = self._music_coordinator.save_saved_text(
            kind, name, content, match_key, existing_id, existing_created_at
        )
        self._refresh_music_saved_text_list(kind)
        self._refresh_music_match_structure_options()
        if widget is not None:
            idx = next((i for i, row in enumerate(updated_rows) if str((row or {}).get("id", "")) == item["id"]), -1)
            if idx >= 0:
                if isinstance(widget, QListWidget):
                    widget.setCurrentRow(idx)
                else:
                    widget.setCurrentCell(idx, 0)
        self._set_music_status(f"Saved {name}")

    def _delete_music_saved_text(self, kind: str) -> None:
        widget, name_edit, match_edit, editor = self._music_text_widget_bundle(kind)
        rows = list(self._music_collection(kind))
        if widget is None:
            return
        idx = int(widget.currentRow() if isinstance(widget, QListWidget) else widget.currentRow() if hasattr(widget, "currentRow") else -1)
        if idx < 0 or idx >= len(rows):
            return
        removed_id = str((rows[idx] or {}).get("id", "")).strip()
        deleted_row = dict(rows[idx])

        updated_rows = []  # Define before use to prevent NameError
        updated_rows = self._music_coordinator.delete_saved_text(kind, removed_id)

        self._refresh_music_saved_text_list(kind)
        self._refresh_music_match_structure_options()
        self._refresh_music_ui()
        if widget is not None and updated_rows:
            next_idx = min(idx, len(updated_rows) - 1)
            if isinstance(widget, QListWidget):
                widget.setCurrentRow(next_idx)
            else:
                widget.setCurrentCell(next_idx, 0)
        if name_edit is not None:
            name_edit.setText("")
        if match_edit is not None:
            if isinstance(match_edit, QComboBox):
                match_edit.setCurrentIndex(0)
            else:
                match_edit.setText("")
        if editor is not None:
            editor.setPlainText("")
        self._set_music_status(f"Deleted {deleted_row.get('name', 'item')}")

    def _load_music_saved_text_into_composer(self, kind: str):
        widget, _, _, _ = self._music_text_widget_bundle(kind)
        rows = self._music_collection(kind)
        idx = widget.currentRow() if widget is not None else -1
        if idx < 0 or idx >= len(rows):
            return
        row = rows[idx] if isinstance(rows[idx], dict) else {}
        content = str(row.get("content", "") or row.get("text", "")).strip()
        if str(kind).startswith("desc"):
            self.music_current_description = content
        else:
            self.music_current_structure = content
        self._persist_music_runtime_state()
        self._refresh_music_ui()
        self._set_primary_page("music")
        self._set_music_status(f"Loaded {str(row.get('name', 'text'))} into composer")

    def _set_music_active_selected(self, kind: str):
        widget, _, _, _ = self._music_text_widget_bundle(kind)
        rows = self._music_collection(kind)
        if widget is None:
            return
        idx = int(widget.currentRow())
        if idx < 0 or idx >= len(rows):
            return
        selected_id = str((rows[idx] or {}).get("id", "")).strip()
        if not selected_id:
            return
        if str(kind).strip().lower().startswith("desc"):
            self._update_music_settings(
                {
                    "activeDescriptionIds": [selected_id],
                    "enabledDescriptionIds": [selected_id],
                    "shuffle": False,
                    "shuffleDescription": False,
                }
            )
        else:
            self._update_music_settings(
                {
                    "activeStructureIds": [selected_id],
                    "enabledStructureIds": [selected_id],
                    "shuffle": False,
                    "shuffleStructure": False,
                }
            )
        self._refresh_music_saved_text_list(kind)
        if isinstance(widget, QListWidget):
            widget.setCurrentRow(idx)
        else:
            widget.setCurrentCell(idx, 0)
        self._set_music_status(f"Set active {str((rows[idx] or {}).get('name', 'item'))}")

    def _get_suno_remaining_credits(self, *, force: bool = False) -> int:
        settings = self._music_settings()
        cache = getattr(self, "_suno_credits_cache", None)
        if not force and isinstance(cache, dict):
            try:
                ts = float(cache.get("checkedAt", 0.0) or 0.0)
                v = cache.get("credits")
                if isinstance(v, int) and (time.time() - ts) < 60.0:
                    return int(v)
            except Exception:
                pass
        from ..services.suno_credits import get_remaining_credits

        credits = int(
            get_remaining_credits(
                api_base_url=self._get_suno_api_base_url(settings),
                api_key="",  # Key managed by Platform API
                timeout_sec=20,
            )
        )
        self._suno_credits_cache = {"credits": credits, "checkedAt": float(time.time())}
        if hasattr(self, "music_suno_credits_label"):
            self.music_suno_credits_label.setText(f"Credits: {credits}")
        if hasattr(self, "header_suno_credits_label"):
            self.header_suno_credits_label.setText(f"Credits: {credits}")
        return credits

    def _get_suno_remaining_credits_fresh(self, *, max_age_sec: float) -> int:
        cache = getattr(self, "_suno_credits_cache", None)
        if isinstance(cache, dict):
            try:
                ts = float(cache.get("checkedAt", 0.0) or 0.0)
                v = cache.get("credits")
                if isinstance(v, int) and (time.time() - ts) <= float(max_age_sec):
                    return int(v)
            except Exception:
                pass
        return int(self._get_suno_remaining_credits(force=True))

    def _start_suno_credits_refresh_async(self, *, force: bool = False):
        def work():
            try:
                self._get_suno_remaining_credits(force=bool(force))
            except Exception:
                QTimer.singleShot(0, lambda: (hasattr(self, "header_suno_credits_label") and self.header_suno_credits_label.setText("Credits: —")))

        threading.Thread(target=work, daemon=True).start()

    def _save_music_draft_state(self):
        drafts = self.music_data.get("songDrafts") if isinstance(self.music_data.get("songDrafts"), list) else []
        if not drafts:
            drafts = [{"id": "draft-01", "title": "", "album": ""}]
            self.music_data["songDrafts"] = drafts
        draft = drafts[0]
        self._persist_setting_patch(
            {
                "musicDraftTitle": str(draft.get("title", "") or ""),
                "musicDraftAlbum": str(draft.get("album", "") or ""),
            }
        )

    def _create_music_inline_toggle(self, label_text: str, on_toggle) -> tuple[QWidget, QPushButton]:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        label = QLabel(label_text)
        self._set_label_role(label, "meta")
        row.addWidget(label)
        toggle = QPushButton("")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_button_role(toggle, "toggle")
        toggle.toggled.connect(lambda checked, btn=toggle: self._sync_toggle_button(btn, checked))
        toggle.toggled.connect(lambda checked: on_toggle(bool(checked)))
        self._sync_toggle_button(toggle, False)
        row.addWidget(toggle)
        return holder, toggle

    def _current_music_song(self) -> dict | None:
        songs = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
        if self.music_current_song_id:
            for song in songs:
                if not isinstance(song, dict):
                    continue
                sid = str(song.get("songUid") or song.get("id") or "").strip()
                if sid == self.music_current_song_id:
                    return song
        if songs:
            last = songs[-1]
            return last if isinstance(last, dict) else None
        return None

    def _update_music_song_record(self, song_id: str, patch: dict) -> dict | None:
        target_id = str(song_id or "").strip()
        if not target_id or not patch:
            return None
        songs = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
        rows = [dict(song) for song in songs if isinstance(song, dict)]
        updated: dict | None = None
        for idx, song in enumerate(rows):
            sid = str(song.get("songUid") or song.get("id") or "").strip()
            if sid != target_id:
                continue
            updated = {**song, **patch}
            rows[idx] = updated
            break
        if not updated:
            return None
        self.music_data["songs"] = rows
        if self.db_cfg:
            try:
                music_upsert_song(self.db_cfg, updated)
            except Exception as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Song database update failed: {exc}")
        return updated

    def _cache_music_song_from_history(self, song: dict) -> dict | None:
        if not isinstance(song, dict):
            return None
        target_uid = str(song.get("songUid") or song.get("id") or "").strip()
        if not target_uid:
            return None
        songs = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
        rows = [dict(x) for x in songs if isinstance(x, dict)]
        updated: dict | None = None
        for idx, row in enumerate(rows):
            rid = str(row.get("songUid") or row.get("id") or "").strip()
            if rid != target_uid:
                continue
            updated = {**row, **song}
            rows[idx] = updated
            break
        if updated is None:
            updated = dict(song)
            rows.append(updated)
        self.music_data["songs"] = rows
        return updated

    def _set_music_generate_running(self, running: bool):
        self._music_generating = bool(running)
        if hasattr(self, "music_generate_button"):
            if running:
                self.music_generate_button.setText("Stop")
                apply_cta_button(self.music_generate_button, "warning", self.ui)
            else:
                self.music_generate_button.setText("Generate")
                apply_cta_button(self.music_generate_button, "success", self.ui)
            self.music_generate_button.setFixedWidth(78)
            self.music_generate_button.setFixedHeight(30)
        if hasattr(self, "workflow_generate_button"):
            try:
                self.workflow_generate_button.setEnabled(not bool(running))
            except Exception:
                pass

    def _append_generated_music_song(self, song: dict):
        songs = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
        rows = [dict(x) for x in songs if isinstance(x, dict)]
        rows.append(song)
        self.music_data["songs"] = rows
        self.music_current_song_id = str(song.get("id", "")).strip() or None
        self.music_current_description = str(song.get("songDescription", "")).strip()
        self.music_current_structure = str(song.get("songStructure", "")).strip()
        drafts = self.music_data.get("songDrafts") if isinstance(self.music_data.get("songDrafts"), list) else []
        if not drafts:
            drafts = [{"id": "draft-01", "title": "", "album": ""}]
            self.music_data["songDrafts"] = drafts
        drafts[0]["title"] = str(song.get("title", "")).strip()
        drafts[0]["album"] = str(song.get("album", "")).strip()
        history = self.music_data.get("history") if isinstance(self.music_data.get("history"), list) else []
        history.append(
            {
                "kind": "song_generated",
                "songId": str(song.get("id", "")).strip(),
                "message": f"{str(song.get('title', '')).strip()} / {str(song.get('album', '')).strip()}",
                "createdAt": str(song.get("createdAt", "")).strip() or now_iso(),
            }
        )
        self.music_data["history"] = history[-500:]
        if self.db_cfg:
            try:
                music_upsert_song(self.db_cfg, song)
            except Exception as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Song database insert failed: {exc}")
        self._persist_music_runtime_state()
        self._refresh_music_ui()

    def _on_music_event(self, event: dict):
        kind = str((event or {}).get("type", "")).strip()
        handler_map = {
            "image_poll_started": self._handle_image_poll_started,
            "auto_video_status": self._handle_auto_video_status,
            "auto_video_done": self._handle_auto_video_done,
            "youtube_connect_select_channel": self._handle_youtube_connect_select_channel,
            "youtube_connect_done": self._handle_youtube_connect_done,
            "youtube_playlists_loaded": self._handle_youtube_playlists_loaded,
            "youtube_upload_status": self._handle_youtube_upload_status,
            "youtube_upload_progress": self._handle_youtube_upload_progress,
            "youtube_upload_done": self._handle_youtube_upload_done,
            "song": self._handle_song,
            "progress": self._handle_progress,
            "status": self._handle_status,
            "lyrics_polished": self._handle_lyrics_polished,
            "suno_result": self._handle_suno_result,
            "suno_poll_result": self._handle_suno_poll_result,
            "suno_schedule_poll": self._handle_suno_schedule_poll,
            "image_poll_result": self._handle_image_poll_result,
            "done": self._handle_done,
        }
        handler = handler_map.get(kind)
        if handler:
            handler(event)

    def _submit_music_song_to_suno(self, song: dict, *, auto: bool = False):
        settings = self._music_settings()

        def work():
            try:
                self._music_coordinator.submit_song_to_suno(song, settings, auto=auto)
            except Exception as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Suno retry failed: {exc}")
                self.bus.music_event.emit({"type": "suno_result", "message": f"Suno failed: {exc}"})

        threading.Thread(target=work, daemon=True).start()

    def _on_music_open_song_folder_clicked(self, song: dict | None = None):
        song = song if isinstance(song, dict) else (self._current_music_song() or {})
        song_uid = str(song.get("songUid", "")).strip()
        if not song_uid:
            QMessageBox.warning(self, "Open Folder", "Select a generated song first.")
            return
        if not self.db_cfg:
            QMessageBox.warning(self, "Open Folder", "Postgres database is not configured. Set Database settings and run Migrate.")
            return
        try:
            result = get_latest_suno_output_dirs_by_song_uid(self.db_cfg, song_uid)
            ok_dir = str(result.get("okDir", "")).strip()
            alt_dir = str(result.get("altDir", "")).strip()
            target = ok_dir or alt_dir
            if not target:
                raise RuntimeError("No output directory recorded for this song yet.")
            if not Path(target).exists():
                raise RuntimeError(f"Output directory does not exist yet: {target}")
            os.startfile(target)
            self._set_music_suno_status(f"Suno folder opened: {Path(target).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Open Folder", str(exc))
            self._set_music_suno_status(f"Suno folder unavailable: {exc}")

    def _music_db_cfg_from_values(self, host: str, port_value, user: str, password: str, database: str) -> DbCfg | None:
        try:
            port = int(port_value)
        except Exception:
            port = 0
        host_text = str(host or "").strip()
        user_text = str(user or "").strip()
        db_text = str(database or "").strip()
        if not host_text or not user_text or not db_text or port <= 0:
            return None
        return DbCfg(host=host_text, port=port, user=user_text, password=str(password or ""), database=db_text)

    def _save_music_api_keys_settings(self):
        """Save API Keys tab (model settings only — AI service keys managed by Platform API)."""
        patch = {
            "slaiSongModel": str(getattr(self, "music_settings_slai_song_model", None).text() or "").strip() or "gpt-5.5",
            "sunoApiBaseUrl": str(getattr(self, "music_settings_suno_api_base_url", None).text() or "").strip(),
            "openaiApiKey": str(getattr(self, "music_settings_openai_key", None).text() or ""),
            "slaiImgModel": str(getattr(self, "music_settings_slai_img_model", None).text() or "").strip() or "cgpt-web/gpt-5.5-pro",
            "falImgModel": str(getattr(self, "music_settings_fal_img_model", None).currentData() or "flux-dev-i2i"),
        }
        self._music_apply_settings_patch(patch, "API Keys settings saved")

    def _save_music_ai_providers_settings(self):
        """Save AI Providers tab (provider selection + YouTube OAuth)."""
        title_album = str(getattr(self, "music_settings_title_album_provider", None).currentData() or "deepseek")
        lyrics_provider = str(getattr(self, "music_settings_lyrics_provider", None).currentData() or "deepseek")
        patch = {
            "songDraftProvider": title_album,
            "titleAlbumProvider": title_album,
            "lyricsProvider": lyrics_provider,
            "youtubeClientId": str(getattr(self, "music_settings_youtube_client_id", None).text() or "").strip(),
            "youtubeClientSecret": str(getattr(self, "music_settings_youtube_client_secret", None).text() or "").strip(),
        }
        self._music_apply_settings_patch(patch, "AI Providers settings saved")

    def _save_music_api_settings(self):
        title_album = str(getattr(self, "music_settings_title_album_provider", None).currentData() or "deepseek") if hasattr(self, "music_settings_title_album_provider") else "deepseek"
        lyrics_provider = str(getattr(self, "music_settings_lyrics_provider", None).currentData() or "deepseek") if hasattr(self, "music_settings_lyrics_provider") else "deepseek"
        patch = {
            "songDraftProvider": str(title_album or "deepseek"),
            "titleAlbumProvider": str(title_album or "deepseek"),
            "lyricsProvider": str(lyrics_provider or "deepseek"),
            "slaiSongModel": str(self.music_settings_slai_song_model.text() or "").strip() or "gpt-5.5",
            "openaiApiKey": str(self.music_settings_openai_key.text() or ""),
            "slaiImgModel": str(self.music_settings_slai_img_model.text() or "").strip() or "cgpt-web/gpt-5.5-pro",
            "sunoApiBaseUrl": str(getattr(self, "music_settings_suno_api_base_url", None).text() or "").strip() if hasattr(self, "music_settings_suno_api_base_url") else "",
            "youtubeClientId": str(getattr(self, "music_settings_youtube_client_id", None).text() or "").strip() if hasattr(self, "music_settings_youtube_client_id") else "",
            "youtubeClientSecret": str(getattr(self, "music_settings_youtube_client_secret", None).text() or "").strip() if hasattr(self, "music_settings_youtube_client_secret") else "",
        }
        self._music_apply_settings_patch(patch, "API settings saved")

    def _save_music_paths_settings(self):
        # Normalize all directory paths to OS-native separators
        def _norm(text):
            t = str(text or "").strip()
            if not t:
                return t
            try:
                return os.path.normpath(t)
            except Exception:
                return t
        patch = {
            "ffmpegPath": str(self.music_settings_ffmpeg_path.text() or "").strip(),
            "downloadsDir": _norm(self.music_settings_downloads_dir.text()),
            "mergedDir": _norm(self.music_settings_merged_dir.text()),
        }
        self._music_apply_settings_patch(patch, "Path settings saved")

    def _save_music_image_settings(self):
        # Normalize all directory paths to OS-native separators
        def _norm(text):
            t = str(text or "").strip()
            if not t:
                return t
            try:
                import os
                return os.path.normpath(t)
            except Exception:
                return t
        patch = {
            "imageBackgroundSamplesDir": _norm(getattr(self, "music_settings_image_bg_samples_dir", None).text()) if hasattr(self, "music_settings_image_bg_samples_dir") else "",
            "imageThumbnailSamplesDir": _norm(getattr(self, "music_settings_image_thumb_samples_dir", None).text()) if hasattr(self, "music_settings_image_thumb_samples_dir") else "",
            "imageOutputDir": _norm(self.music_settings_image_output_dir.text()),
            "imageResolution": str(self.music_settings_image_resolution.currentData() or "1920x1080"),
            "outputResolution": str(self.music_settings_image_resolution.currentData() or "1920x1080"),
            "styleStrength": int(self.music_settings_style_strength.value() or 60),
            "backgroundSourceMode": str(self.music_settings_background_source_mode.currentData() or "samples"),
            "thumbnailOverlayMode": str(self.music_settings_thumbnail_overlay_mode.currentData() or "ai"),
            "imageBackgroundProvider": str(getattr(self, "music_settings_image_bg_provider", None).currentData() or "slai") if hasattr(self, "music_settings_image_bg_provider") else "slai",
            "imageThumbnailProvider": str(getattr(self, "music_settings_image_thumb_provider", None).currentData() or "slai") if hasattr(self, "music_settings_image_thumb_provider") else "slai",
        }
        self._music_apply_settings_patch(patch, "Image settings saved")
        try:
            ow, oh = self._resolved_output_resolution()
            if hasattr(self, "image_bg_preview_box") and hasattr(self.image_bg_preview_box, "set_ratio"):
                self.image_bg_preview_box.set_ratio(int(ow), int(oh))
            if hasattr(self, "image_thumb_preview_box") and hasattr(self.image_thumb_preview_box, "set_ratio"):
                self.image_thumb_preview_box.set_ratio(int(ow), int(oh))
            if hasattr(self, "preview_box") and hasattr(self.preview_box, "set_ratio"):
                self.preview_box.set_ratio(int(ow), int(oh))
        except Exception:
            pass

    def _save_music_suno_settings(self):
        """Delegate Suno settings save to the music settings coordinator."""
        patch = self.music_settings_coordinator.gather_suno_settings_patch()
        previous_output_dir = str(self._music_settings().get('sunoOutputDir', '')).strip()
        new_output_dir = str(patch.get('sunoOutputDir', '')).strip()

        if new_output_dir and new_output_dir != previous_output_dir:
            Path(str(new_output_dir)).mkdir(parents=True, exist_ok=True)

        self._persist_setting_patch(patch)
        self._log(f"[{time.strftime('%H:%M:%S')}] Music Suno settings saved")
        self.bus.music_event.emit({'type': 'settings_updated'})
        self._set_music_status("Music settings saved successfully")
        self._set_music_settings_status("Music settings saved successfully")

        if self.db_cfg:
            try:
                self._remap_pending_suno_task_output_dirs(previous_output_dir, new_output_dir)
            except Exception as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Suno pending path remap skipped: {exc}")
        self._start_suno_credits_refresh_async(force=True)

    def _open_music_settings_subtab(self, subtab_key: str) -> None:
        """Switch to the Settings page and select a named music-settings subtab.

        Reconstructed (task 11.3 repair): navigates to the settings primary page
        then activates the tab whose label matches ``subtab_key`` (e.g. "suno",
        "descriptions", "structures") case-insensitively.
        """
        self._set_primary_page("settings")
        tabs = getattr(self, "music_settings_tabs", None)
        if tabs is None:
            return
        target = str(subtab_key or "").strip().lower()
        if not target:
            return
        for i in range(tabs.count()):
            if str(tabs.tabText(i) or "").strip().lower() == target:
                tabs.setCurrentIndex(i)
                return

    def _remap_pending_suno_task_output_dirs(self, previous_output_dir: str, new_output_dir: str) -> None:
        """Remap pending Suno task output dirs after the output folder changes.

        Reconstructed (task 11.3 repair): delegates to the music_db helper so
        pending tasks created under the old base dir resolve to the new one.
        """
        old_base = str(previous_output_dir or "").strip()
        new_base = str(new_output_dir or "").strip()
        if not self.db_cfg or not new_base or old_base == new_base:
            return
        remap_pending_suno_output_dirs(self.db_cfg, old_base_dir=old_base, new_base_dir=new_base)

    def _save_music_db_settings(self) -> None:
        """Database connection settings are read-only (configured via .env).

        Reconstructed (task 11.3 repair): the Database settings tab fields are
        read-only/disabled, so there is nothing to persist; surface a status
        message matching the other ``_save_music_*_settings`` handlers.
        """
        self._set_music_status("Database connection is configured via .env (read-only)")
        self._set_music_settings_status("Database settings are read-only; configure via .env")

    def _on_music_settings_save_clicked(self):
        current = str(self.music_settings_tabs.tabText(self.music_settings_tabs.currentIndex()) or "").strip().lower() if hasattr(self, "music_settings_tabs") else "api"
        if current == "api keys":
            self._save_music_api_keys_settings()
        elif current == "ai providers":
            self._save_music_ai_providers_settings()
        elif current == "profiles":
            self._save_music_settings_profile()
        elif current == "paths":
            self._save_music_paths_settings()
        elif current == "image":
            self._save_music_image_settings()
        elif current == "database":
            self._save_music_db_settings()
        elif current == "suno":
            self._save_music_suno_settings()
        elif current == "youtube":
            self._set_music_status("YouTube settings save inline in the tab")
        elif current == "pools":
            self._set_music_status("Pools settings save inline")
        else:
            self._set_music_status("This Settings tab saves with its own inline actions")

    def _on_music_settings_tab_changed(self):
        if not hasattr(self, "music_settings_tabs"):
            return
        current = str(self.music_settings_tabs.tabText(self.music_settings_tabs.currentIndex()) or "").strip().lower()
        inline_tabs = {"profiles", "descriptions", "structures", "pools", "youtube", "performance"}
        if hasattr(self, "music_settings_footer_save_button"):
            self.music_settings_footer_save_button.setVisible(current not in inline_tabs)
        if current == "pools" and getattr(self, "_music_pools_dirty", False):
            self._music_pools_dirty = False
            self._music_controller.refresh_music_pool_stats(force=True)
            self._music_controller.refresh_music_pool_table(force=True)
        if current == "youtube":
            self._youtube_oauth_controller.refresh_youtube_oauth_apps_table()

    def _reset_music_local_data(self):
        if self.db_cfg:
            try:
                self.persistence_coordinator.reload_persisted_state()
                self._refresh_music_ui()
                self._set_music_settings_status("Reloaded from database")
                return
            except Exception as exc:
                self._set_music_settings_status(f"Reload failed: {exc}")
                return
        if QMessageBox.question(self, "Reset", "Reset Python Music app local data to defaults?") != QMessageBox.StandardButton.Yes:
            return
        self.music_data = default_music_app_data()
        self.music_current_description = str((self.music_data.get("descriptions") or [{}])[0].get("content", "")).strip()
        self.music_current_structure = str((self.music_data.get("structures") or [{}])[0].get("content", "")).strip()
        self.music_current_song_id = None
        self._music_settings_selected_profile_id = None
        self._save_music_app_data()
        self._refresh_music_ui()
        self._set_music_settings_status("Music local data reset")

    def _refresh_music_settings_profile_list_impl(self):
        if not hasattr(self, "music_settings_profile_list"):
            return
        rows = self._music_profiles()
        current = str(getattr(self, "_music_settings_selected_profile_id", "") or "").strip()
        self.music_settings_profile_list.blockSignals(True)
        self.music_settings_profile_list.clear()
        for profile in rows:
            item = QListWidgetItem(str(profile.get("name", "Unnamed Profile")))
            item.setData(Qt.ItemDataRole.UserRole, str(profile.get("id", "")).strip())
            self.music_settings_profile_list.addItem(item)
        self.music_settings_profile_list.blockSignals(False)
        if rows and not current:
            current = str(rows[0].get("id", "")).strip()
        self._music_settings_selected_profile_id = current or None
        for idx in range(self.music_settings_profile_list.count()):
            item = self.music_settings_profile_list.item(idx)
            if str(item.data(Qt.ItemDataRole.UserRole) or "").strip() == current:
                self.music_settings_profile_list.setCurrentRow(idx)
                self.music_settings_profile_list.scrollToItem(item)
                break
        self._load_music_settings_profile_details()

    def _refresh_music_settings_profile_video_templates(self, selected_id: str) -> None:
        combo = getattr(self, "music_settings_profile_video_template", None)
        if combo is None:
            return
        key = str(selected_id or "").strip()
        rows = []
        if self.db_cfg:
            try:
                rows = db_list_video_templates(self.db_cfg)
                write_local_templates(rows)
            except Exception:
                rows = read_local_templates()
        else:
            rows = read_local_templates()
        items = [(str(r.id), str(r.name or r.id)) for r in rows]
        combo.blockSignals(True)
        combo.clear()
        if not self.db_cfg:
            combo.addItem("(Database not configured)", userData="")
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            combo.setEnabled(False)
            return
        combo.setEnabled(True)
        combo.addItem("No template", userData="")
        for tpl_id, name in items:
            if not tpl_id:
                continue
            combo.addItem(f"{name} · {tpl_id}", userData=tpl_id)
        if key and combo.findData(key) < 0:
            combo.addItem(f"Missing · {key}", userData=key)
        idx = combo.findData(key) if key else 0
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _refresh_music_settings_profile_reel_templates(self, selected_id: str) -> None:
        combo = getattr(self, "music_settings_profile_reel_template", None)
        if combo is None:
            return
        key = str(selected_id or "").strip()
        rows = []
        if self.db_cfg:
            try:
                rows = db_list_video_templates(self.db_cfg, kind="reel")
            except Exception:
                rows = []
        items = [(str(r.id), str(r.name or r.id)) for r in rows]
        combo.blockSignals(True)
        combo.clear()
        if not self.db_cfg:
            combo.addItem("(Database not configured)", userData="")
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            combo.setEnabled(False)
            return
        combo.setEnabled(True)
        combo.addItem("No template", userData="")
        for tpl_id, name in items:
            if not tpl_id:
                continue
            combo.addItem(f"{name} · {tpl_id}", userData=tpl_id)
        if key and combo.findData(key) < 0:
            combo.addItem(f"Missing · {key}", userData=key)
        idx = combo.findData(key) if key else 0
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _refresh_music_settings_profile_youtube_oauth_apps(self, selected_id: str) -> None:
        combo = getattr(self, "music_settings_profile_youtube_oauth_app", None)
        if combo is None:
            return
        key = str(selected_id or "").strip()
        rows = []
        if self.db_cfg:
            try:
                from ..features.youtube.db import db_list_youtube_oauth_apps

                rows = db_list_youtube_oauth_apps(self.db_cfg, limit=500)
            except Exception:
                rows = []
        combo.blockSignals(True)
        combo.clear()
        if not self.db_cfg:
            combo.addItem("(Database not configured)", userData="")
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            combo.setEnabled(False)
            return
        combo.setEnabled(True)
        combo.addItem("Use global settings", userData="")
        items = [(str(r.id), str(r.name or r.id)) for r in rows]
        for oid, name in items:
            if not oid:
                continue
            combo.addItem(f"{name} · {oid}", userData=oid)
        if key and combo.findData(key) < 0:
            combo.addItem(f"Missing · {key}", userData=key)
        idx = combo.findData(key) if key else 0
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _on_music_profile_youtube_visibility_changed(self):
        mode = "unlisted"
        if hasattr(self, "music_settings_profile_youtube_visibility"):
            mode = str(self.music_settings_profile_youtube_visibility.currentData() or "unlisted").strip() or "unlisted"
        show = mode == "scheduled"
        row = getattr(self, "music_settings_profile_youtube_publish_row", None)
        if row is not None:
            row.setVisible(show)
        if hasattr(self, "music_settings_profile_youtube_publish_date"):
            self.music_settings_profile_youtube_publish_date.setVisible(False)
        if hasattr(self, "music_settings_profile_youtube_publish_hour"):
            self.music_settings_profile_youtube_publish_hour.setVisible(show)
        if hasattr(self, "music_settings_profile_youtube_publish_minute"):
            self.music_settings_profile_youtube_publish_minute.setVisible(show)

    def _refresh_music_history_table(self, force: bool = False):
        if not hasattr(self, "music_history_table"):
            return
        if getattr(self, "_current_primary_page", "") != "music":
            if not force:
                self._music_history_dirty = True
                return
        self._music_history_dirty = False
        # Skip if a refresh is already inflight
        if getattr(self, "_music_history_refresh_inflight", False):
            return
        self._music_history_refresh_inflight = True

        from_text = str(getattr(self, "music_history_from_date", "") or "").strip()
        to_text = str(getattr(self, "music_history_to_date", "") or "").strip()
        db_cfg = self.db_cfg
        music_data = self.music_data
        latest_batch_only = bool(self.music_last_batch_only)

        def fetch():
            try:
                table_rows, suno_latest = self.music_history_coordinator.load_history_rows(
                    db_cfg=db_cfg,
                    music_data=music_data,
                    from_ymd=from_text,
                    to_ymd=to_text,
                    limit=5000,
                    latest_batch_only=latest_batch_only,
                    list_songs_for_history_fn=list_songs_for_history,
                    list_latest_suno_tasks_by_song_uids_fn=list_latest_suno_tasks_by_song_uids,
                )
                self.bus.ui_invoke.emit(lambda: self._apply_music_history_rows(table_rows, suno_latest))
            except Exception:
                self.bus.ui_invoke.emit(lambda: setattr(self, "_music_history_refresh_inflight", False))

        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_music_history_rows(self, table_rows: list, suno_latest: dict):
        """Apply pre-fetched history data to the table widget (UI thread only)."""
        self._music_history_refresh_inflight = False
        self.music_history_rows = table_rows
        self.music_history_suno_latest = suno_latest
        table = self.music_history_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        table.setRowCount(0)
        table.clearSpans()
        table.setRowCount(len(table_rows))
        current_song_id = str(self.music_current_song_id or "").strip()
        _cache = getattr(self, "_svg_icon_cache", None)
        if _cache is None:
            _cache = {}
            self._svg_icon_cache = _cache
        folder_icon = render_svg_icon(self._lucide_icon_path("folder-open"), 14, self.ui["text"], cache=_cache)
        retry_icon = render_svg_icon(self._lucide_icon_path("rotate-cw"), 14, self.ui["text"], cache=_cache)

        def _build_channel_cell(*, name: str, tooltip: str, enabled: bool, on_open):
            host = QWidget()
            layout = QHBoxLayout(host)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(6)
            label = QLabel(name)
            label.setToolTip(tooltip)
            self._set_label_role(label, "meta")
            layout.addWidget(label, 1)
            btn = QPushButton()
            self._set_button_role(btn, "tableIcon")
            btn.setFixedSize(22, 22)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setToolTip("Open folder")
            btn.setIcon(folder_icon)
            btn.setIconSize(QSize(14, 14))
            btn.setEnabled(bool(enabled))
            btn.clicked.connect(on_open)
            layout.addWidget(btn, 0)
            layout.setAlignment(btn, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return host

        def _build_suno_cell(*, color: str, tooltip: str, on_retry):
            host = QWidget()
            layout = QHBoxLayout(host)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(6)
            dot = QLabel()
            dot.setToolTip(tooltip)
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
            layout.addWidget(dot, 0)
            layout.setAlignment(dot, Qt.AlignmentFlag.AlignVCenter)
            layout.addStretch(1)
            retry_btn = QPushButton()
            self._set_button_role(retry_btn, "tableIcon")
            retry_btn.setFixedSize(22, 22)
            retry_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            retry_btn.setToolTip("Retry Suno")
            retry_btn.setIcon(retry_icon)
            retry_btn.setIconSize(QSize(14, 14))
            retry_btn.clicked.connect(on_retry)
            layout.addWidget(retry_btn, 0)
            layout.setAlignment(retry_btn, Qt.AlignmentFlag.AlignVCenter)
            return host

        def _build_batch_separator(*, batch_id: str, run_date: str, generated_at: str):
            host = QWidget()
            host.setStyleSheet(f"background-color: {self.ui['primary_pressed']};")
            layout = QHBoxLayout(host)
            layout.setContentsMargins(8, 2, 8, 2)
            layout.setSpacing(6)
            gen = str(generated_at or "").replace("T", " ")[:16]
            label = QLabel(f"Batch: {batch_id}  •  Generated: {gen or '-'}  •  Run Date: {run_date or '-'}")
            label.setStyleSheet(f"color: {self.ui['text_soft']}; font-size: 11px; font-weight: 800;")
            layout.addWidget(label, 1)
            return host

        song_no = 0
        for row_idx, row in enumerate(table_rows):
            if isinstance(row, dict) and bool(row.get("__separator__", False)):
                batch_id = str(row.get("batchId", "")).strip() or "-"
                run_date = str(row.get("runDate", "")).strip()
                generated_at = str(row.get("generatedAt", "")).strip()
                for col_idx in range(9):
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    item.setBackground(QColor(self.ui["primary_pressed"]))
                    table.setItem(row_idx, col_idx, item)
                table.setCellWidget(row_idx, 0, _build_batch_separator(batch_id=batch_id, run_date=run_date, generated_at=generated_at))
                table.setSpan(row_idx, 0, 1, 9)
                table.setRowHeight(row_idx, 28)
                continue

            song = row if isinstance(row, dict) else {}
            song_no += 1
            ok_name = str(song.get("profileOkName", "")).strip() or str(song.get("profileOkId", "")).strip()
            alt_name = str(song.get("profileAltName", "")).strip() or str(song.get("profileAltId", "")).strip()
            suno_row = suno_latest.get(str(song.get("songUid", "")).strip())
            suno_status = ""
            suno_tooltip = ""
            if isinstance(suno_row, dict):
                raw_status = str(suno_row.get("status", "")).strip() or "PENDING"
                ok_url = str(suno_row.get("audioUrlOk") or "").strip()
                alt_url = str(suno_row.get("audioUrlAlt") or "").strip()
                if ok_url and alt_url:
                    suno_status = "READY"
                else:
                    m = re.search(r"(\d{3,6})", raw_status)
                    if raw_status.upper().startswith("FAIL") and m:
                        suno_status = f"ERR {m.group(1)}"
                    else:
                        suno_status = raw_status
                suno_tooltip = raw_status
            elif suno_row is None:
                suno_status = ""
            values = [
                str(song_no),
                str(song.get("album", "")).strip(),
                str(song.get("title", "")).strip(),
                str(song.get("songDescriptionTitle", "")).strip() or "-",
                str(song.get("songStructureTitle", "")).strip() or "-",
                ok_name or "-",
                alt_name or "-",
                "",
                str(song.get("createdAt", "")).replace("T", " ")[:16],
            ]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, str(song.get("songUid", "")).strip())
                table.setItem(row_idx, col_idx, item)

            ok_dir = str((suno_row or {}).get("outputDirOk", "")).strip() if isinstance(suno_row, dict) else ""
            alt_dir = str((suno_row or {}).get("outputDirAlt", "")).strip() if isinstance(suno_row, dict) else ""

            table.setCellWidget(
                row_idx,
                5,
                _build_channel_cell(
                    name=ok_name or "-",
                    tooltip=ok_name or "-",
                    enabled=bool(ok_dir),
                    on_open=lambda _=False, idx=row_idx, payload=dict(song): self._music_controller.on_music_history_open_ok_folder_clicked(idx, payload),
                ),
            )
            table.setCellWidget(
                row_idx,
                6,
                _build_channel_cell(
                    name=alt_name or "-",
                    tooltip=alt_name or "-",
                    enabled=bool(alt_dir),
                    on_open=lambda _=False, idx=row_idx, payload=dict(song): self._music_controller.on_music_history_open_alt_folder_clicked(idx, payload),
                ),
            )

            from pathlib import Path
            dot_color = self.ui["text_muted"]
            status_up = str(suno_status or "").upper()
            has_suno_row = isinstance(suno_row, dict)
            has_ok_url = bool(str((suno_row or {}).get("audioUrlOk") or "").strip()) if has_suno_row else False
            has_alt_url = bool(str((suno_row or {}).get("audioUrlAlt") or "").strip()) if has_suno_row else False
            ok_dir = str((suno_row or {}).get("outputDirOk", "")).strip() if has_suno_row else ""
            alt_dir = str((suno_row or {}).get("outputDirAlt", "")).strip() if has_suno_row else ""
            # Use downloaded flags from DB instead of expensive filesystem iteration
            has_ok_downloaded = bool((suno_row or {}).get("downloadedOk", False)) if has_suno_row else False
            has_alt_downloaded = bool((suno_row or {}).get("downloadedAlt", False)) if has_suno_row else False
            if status_up in ("READY", "SUCCESS", "COMPLETE", "COMPLETED", "DONE") or (has_suno_row and (has_ok_url or has_alt_url)) or has_ok_downloaded or has_alt_downloaded:
                dot_color = self.ui["success_border"]
            elif (
                status_up.startswith("ERR")
                or status_up.startswith("FAILED")
                or status_up.startswith("FAIL")
                or status_up.endswith("_FAILED")
                or "FAILED" in status_up
                or "ERROR" in status_up
            ):
                dot_color = self.ui["danger_border"]
            elif status_up in ("PENDING", "SUBMITTED", "PROCESSING", "STREAMING", "QUEUED") or has_suno_row:
                dot_color = self.ui["warning_border"]

            dot_tip = suno_tooltip or ""
            if not dot_tip and suno_status:
                dot_tip = suno_status

            table.setCellWidget(
                row_idx,
                7,
                _build_suno_cell(
                    color=dot_color,
                    tooltip=dot_tip,
                    on_retry=lambda _=False, idx=row_idx, payload=dict(song): self._music_controller.on_music_history_retry_suno_clicked(idx, payload),
                ),
            )
            if str(song.get("songUid", "")).strip() == current_song_id:
                table.selectRow(row_idx)
        table.setColumnWidth(0, 36)
        table.setColumnWidth(1, 220)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 90)
        table.setColumnWidth(5, 180)
        table.setColumnWidth(6, 180)
        table.setColumnWidth(7, 88)
        table.setColumnWidth(8, 132)
        table.blockSignals(False)
        table.setUpdatesEnabled(True)

    def _on_music_history_row_selected(self):
        if not hasattr(self, "music_history_table"):
            return
        row = int(self.music_history_table.currentRow())
        rows = list(getattr(self, "music_history_rows", []) or [])
        if row < 0 or row >= len(rows):
            return
        song = rows[row]
        if isinstance(song, dict) and bool(song.get("__separator__", False)):
            return
        if not isinstance(song, dict):
            return

        desc = str(song.get("song_description", "") or song.get("songDescription", "")).strip()
        struct = str(song.get("song_structure", "") or song.get("songStructure", "")).strip()
        lyrics = str(song.get("lyrics_polished", "") or song.get("lyrics_raw", "") or song.get("lyricsPolished", "") or song.get("lyricsRaw", "")).strip()

        if not desc or not struct or not lyrics:
            song_uid = str(song.get("songUid") or "").strip()
            local = self.music_data.get("songs") if isinstance(self.music_data.get("songs"), list) else []
            for s in local:
                if not isinstance(s, dict):
                    continue
                sid = str(s.get("songUid") or s.get("id") or "").strip()
                if sid != song_uid:
                    continue
                if not desc:
                    desc = str(s.get("song_description", "") or s.get("songDescription", "")).strip()
                if not struct:
                    struct = str(s.get("song_structure", "") or s.get("songStructure", "")).strip()
                if not lyrics:
                    lyrics = str(s.get("lyrics_polished", "") or s.get("lyrics_raw", "") or s.get("lyricsPolished", "") or s.get("lyricsRaw", "")).strip()
                break

        title = str(song.get("title", "")).strip()
        album = str(song.get("album", "")).strip()

        self._music_ui_loading = True
        try:
            if hasattr(self, "music_description_editor"):
                self.music_description_editor.setPlainText(desc)
            if hasattr(self, "music_structure_editor"):
                self.music_structure_editor.setPlainText(struct)
            if hasattr(self, "music_song_lyrics_editor"):
                self.music_song_lyrics_editor.setPlainText(lyrics)
            if hasattr(self, "music_draft_title"):
                self.music_draft_title.setText(title)
            if hasattr(self, "music_draft_album"):
                self.music_draft_album.setText(album)
        finally:
            self._music_ui_loading = False

        self.music_current_description = desc
        self.music_current_structure = struct
        self.music_current_song_id = str(song.get("songUid") or "").strip() or None
        self._cache_music_song_from_history(song)

        drafts = self.music_data.get("songDrafts") if isinstance(self.music_data.get("songDrafts"), list) else []
        if not drafts:
            drafts = [{"id": "draft-01", "title": "", "album": ""}]
            self.music_data["songDrafts"] = drafts
        drafts[0]["title"] = title
        drafts[0]["album"] = album
        self._persist_music_runtime_state()

        song_uid = str(song.get("songUid", "")).strip()
        suno_row = (getattr(self, "music_history_suno_latest", {}) or {}).get(song_uid)
        msg = ""
        tip = ""
        if isinstance(suno_row, dict):
            raw_status = str(suno_row.get("status", "")).strip()
            ok_url = str(suno_row.get("audioUrlOk") or "").strip()
            alt_url = str(suno_row.get("audioUrlAlt") or "").strip()
            status = "READY" if ok_url and alt_url else (raw_status or "PENDING")
            msg = f"Suno: {status}"
            if raw_status:
                tip = raw_status
        if msg:
            self._set_music_suno_status(msg if not tip else f"{msg} ({tip})" if tip != msg.replace("Suno: ", "") else msg)
            if hasattr(self, "footer_left_label") and tip:
                self.footer_left_label.setToolTip(tip)
        else:
            self._set_music_suno_status("")
            if hasattr(self, "footer_left_label"):
                self.footer_left_label.setToolTip("")

        self._set_music_status(f"Loaded song: {title or 'Untitled'}")

    def _on_music_history_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        table = getattr(self, "music_history_table", None)
        if table is None:
            return
        row = int(table.currentRow())
        rows = list(getattr(self, "music_history_rows", []) or [])
        if row < 0 or row >= len(rows):
            return
        song = rows[row]
        if not isinstance(song, dict) or bool(song.get("__separator__", False)):
            return

        suno_row = (getattr(self, "music_history_suno_latest", {}) or {}).get(str(song.get("songUid", "")).strip())
        ok_dir = str((suno_row or {}).get("outputDirOk", "")).strip() if isinstance(suno_row, dict) else ""
        alt_dir = str((suno_row or {}).get("outputDirAlt", "")).strip() if isinstance(suno_row, dict) else ""
        ok_url = str((suno_row or {}).get("audioUrlOk") or "").strip() if isinstance(suno_row, dict) else ""
        alt_url = str((suno_row or {}).get("audioUrlAlt") or "").strip() if isinstance(suno_row, dict) else ""
        has_mp3 = bool(ok_url) or bool(alt_url)

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1a2a41; color: #dbe7fb; border: 1px solid #2a4060; border-radius: 8px; padding: 4px; }"
            "QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }"
            "QMenu::item:selected { background: #2a66d9; color: #ffffff; }"
            "QMenu::separator { height: 1px; background: #2a4060; margin: 4px 8px; }"
        )

        refresh = menu.addAction("Refresh History")
        refresh.triggered.connect(lambda: self._refresh_music_history_table(force=True))

        menu.addSeparator()

        title = str(song.get("title", "")).strip()
        album = str(song.get("album", "")).strip()
        song_uid = str(song.get("songUid", "")).strip()
        batch_id = str(song.get("batchId", "")).strip()

        copy_title = menu.addAction("Copy Title")
        copy_title.triggered.connect(lambda _, t=title: QApplication.clipboard().setText(t))
        copy_album = menu.addAction("Copy Album")
        copy_album.triggered.connect(lambda _, t=album: QApplication.clipboard().setText(t))
        copy_uid = menu.addAction("Copy Song UID")
        copy_uid.triggered.connect(lambda _, t=song_uid: QApplication.clipboard().setText(t))
        copy_batch = menu.addAction("Copy Batch ID")
        copy_batch.triggered.connect(lambda _, t=batch_id: QApplication.clipboard().setText(t))

        menu.addSeparator()

        open_ok = menu.addAction("Open OK Folder")
        open_ok.setEnabled(bool(ok_dir))
        open_ok.triggered.connect(lambda _, idx=row, payload=dict(song): self._music_controller.on_music_history_open_ok_folder_clicked(idx, payload))

        open_alt = menu.addAction("Open ALT Folder")
        open_alt.setEnabled(bool(alt_dir))
        open_alt.triggered.connect(lambda _, idx=row, payload=dict(song): self._music_controller.on_music_history_open_alt_folder_clicked(idx, payload))

        menu.addSeparator()

        retry_suno = menu.addAction("Retry Suno")
        retry_suno.setEnabled(True)
        retry_suno.triggered.connect(lambda _, idx=row, payload=dict(song): self._music_controller.on_music_history_retry_suno_clicked(idx, payload))

        menu.addSeparator()

        hide_batch = menu.addAction("Hide Batch")
        hide_batch.triggered.connect(lambda _, payload=dict(song): self._on_music_history_hide_batch_clicked(payload))

        menu.exec(table.viewport().mapToGlobal(pos))

    def _on_music_history_hide_batch_clicked(self, song: dict):
        batch_id = str(song.get("batchId", "")).strip()
        if not batch_id:
            QMessageBox.warning(self, "Hide Batch", "No batch ID found for this song.")
            return
        if QMessageBox.question(self, "Hide Batch", f"Hide entire batch '{batch_id}' from history?\n\nThis will also delete all files and related data.") != QMessageBox.StandardButton.Yes:
            return
        if not self.db_cfg:
            QMessageBox.warning(self, "Hide Batch", "Postgres database is not configured.")
            return
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QLabel
        try:
            from ..database.music_db import hide_batch

            progress = QLabel("Hiding batch...", self)
            progress.setStyleSheet("color: #dbe7fb; font-size: 13px; padding: 20px;")
            progress.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
            progress.show()

            class HideWorker(QThread):
                def __init__(inner_self):
                    super().__init__()
                    inner_self.result = None
                    inner_self.error = None
                def run(inner_self):
                    try:
                        inner_self.result = hide_batch(self.db_cfg, batch_id)
                    except Exception as exc:
                        inner_self.error = str(exc)

            worker = HideWorker()
            worker.finished.connect(lambda: self._music_controller.on_music_hide_batch_done(worker, batch_id, progress))
            worker.start()
        except Exception as exc:
            QMessageBox.warning(self, "Hide Batch", f"Failed: {exc}")

    def _on_music_open_song_channel_folder_clicked(self, song: dict | None = None, *, channel: str = "ok"):
        song = song if isinstance(song, dict) else (self._current_music_song() or {})
        song_uid = str(song.get("songUid", "")).strip()
        if not song_uid:
            QMessageBox.warning(self, "Open Folder", "Select a generated song first.")
            return
        if not self.db_cfg:
            QMessageBox.warning(self, "Open Folder", "Postgres database is not configured. Set Database settings and run Migrate.")
            return
        kind = str(channel or "ok").strip().lower()
        try:
            result = get_latest_suno_output_dirs_by_song_uid(self.db_cfg, song_uid)
            ok_dir = str(result.get("okDir", "")).strip()
            alt_dir = str(result.get("altDir", "")).strip()
            target = ok_dir if kind == "ok" else alt_dir if kind == "alt" else (ok_dir or alt_dir)
            if not target:
                raise RuntimeError("No output directory recorded for this song yet.")
            if not Path(target).exists():
                raise RuntimeError(f"Output directory does not exist yet: {target}")
            os.startfile(target)
            label = "OK" if kind == "ok" else "ALT" if kind == "alt" else "Suno"
            self._set_music_suno_status(f"{label} folder opened: {Path(target).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Open Folder", str(exc))
            self._set_music_suno_status(f"Folder unavailable: {exc}")

    def _refresh_music_runtime_controls(self, settings: dict):
        widget_factory.set_calendar_picker_value(getattr(self, "music_run_from_input", None), getattr(self, "music_run_from_date", ""))
        widget_factory.set_calendar_picker_value(getattr(self, "music_run_to_input", None), getattr(self, "music_run_to_date", ""))
        widget_factory.set_calendar_picker_value(getattr(self, "music_history_from_input", None), getattr(self, "music_history_from_date", ""))
        widget_factory.set_calendar_picker_value(getattr(self, "music_history_to_input", None), getattr(self, "music_history_to_date", ""))
        if hasattr(self, "music_language_combo"):
            self.music_language_combo.setCurrentText(str(settings.get("language", "English")))
        title_album_provider = str(settings.get("titleAlbumProvider", "") or settings.get("songDraftProvider", "deepseek")).strip() or "deepseek"
        lyrics_provider = str(settings.get("lyricsProvider", "") or title_album_provider).strip() or title_album_provider
        if hasattr(self, "music_settings_title_album_provider"):
            idx = self.music_settings_title_album_provider.findData(title_album_provider)
            self.music_settings_title_album_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "music_settings_lyrics_provider"):
            idx = self.music_settings_lyrics_provider.findData(lyrics_provider)
            self.music_settings_lyrics_provider.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "music_settings_suno_api_base_url"):
            self.music_settings_suno_api_base_url.setText(str(settings.get("sunoApiBaseUrl", "https://api.sunoapi.org") or "https://api.sunoapi.org").strip())
        if hasattr(self, "music_creativity_slider"):
            self.music_creativity_slider.setValue(int(settings.get("creativity", 55) or 55))
        if hasattr(self, "music_creativity_value"):
            self.music_creativity_value.setText(str(int(settings.get("creativity", 55) or 55)))
        if hasattr(self, "music_count_spin"):
            self.music_count_spin.setValue(int(settings.get("defaultSongCount", 1) or 1))
        if hasattr(self, "music_strict_combo"):
            self.music_strict_combo.setCurrentText(str(int(settings.get("strictLevel", 3) or 3)))
        if hasattr(self, "music_history_combo"):
            self.music_history_combo.setCurrentText(str(int(settings.get("uniquenessHistoryWindow", 100) or 100)))
        if hasattr(self, "music_history_last_batch"):
            self.music_history_last_batch.setChecked(bool(self.music_last_batch_only))
        self._apply_music_toggle_state(getattr(self, "music_unique_opening", None), bool(settings.get("uniqueOpening", False)))
        self._apply_music_toggle_state(getattr(self, "music_match_desc_struct", None), bool(settings.get("matchDescriptionStructure", False)))
        self._apply_music_toggle_state(getattr(self, "music_shuffle_description", None), bool(settings.get("shuffleDescription", False)))
        self._apply_music_toggle_state(getattr(self, "music_shuffle_structure", None), bool(settings.get("shuffleStructure", False)))
        self._apply_music_toggle_state(getattr(self, "music_cycle_structures", None), bool(settings.get("cycleStructures", False)))
        self._apply_music_toggle_state(getattr(self, "music_all_descriptions", None), bool(settings.get("useAllDescriptions", False)))
        self._apply_music_toggle_state(getattr(self, "music_all_structures", None), bool(settings.get("useAllStructures", False)))
        self._apply_music_toggle_state(getattr(self, "music_auto_gen_image_toggle", None), bool(settings.get("autoGenImage", True)))
        self._apply_music_toggle_state(getattr(self, "music_auto_gsuno_toggle", None), bool(settings.get("autoGSuno", False)))
        self._apply_music_toggle_state(getattr(self, "music_auto_video_toggle", None), bool(settings.get("autoVideoAfterSuno", False)))
        self._apply_music_toggle_state(getattr(self, "music_auto_merge_toggle", None), bool(settings.get("autoMergeAfterVideo", False)))
        self._apply_music_toggle_state(getattr(self, "music_auto_reel_toggle", None), bool(settings.get("autoReelAfterVideo", False)))
        self._apply_music_toggle_state(getattr(self, "music_auto_upload_youtube_toggle", None), bool(settings.get("autoUploadYouTube", False)))
        self._sync_image_auto_poll_timer()
        self._sync_auto_video_timer()
        self._sync_youtube_auto_poll_timer()
        if hasattr(self, "music_polish_slider"):
            self.music_polish_slider.setValue(int(settings.get("lyricsPolishStrength", 60) or 60))
        if hasattr(self, "music_polish_value"):
            self.music_polish_value.setText(str(int(settings.get("lyricsPolishStrength", 60) or 60)))

    def _refresh_music_editor_state(self, settings: dict | None = None):
        settings = settings if isinstance(settings, dict) else self._music_settings()
        drafts = self.music_data.get("songDrafts") if isinstance(self.music_data.get("songDrafts"), list) else []
        draft = drafts[0] if drafts else {"title": "", "album": ""}
        if hasattr(self, "music_draft_title"):
            self.music_draft_title.setText(str(draft.get("title", "")).strip())
        if hasattr(self, "music_draft_album"):
            self.music_draft_album.setText(str(draft.get("album", "")).strip())
        if hasattr(self, "music_description_editor"):
            self.music_description_editor.setPlainText(self.music_current_description)
        if hasattr(self, "music_structure_editor"):
            self.music_structure_editor.setPlainText(self.music_current_structure)
        song = self._current_music_song() or {}
        lyrics = str(song.get("lyricsPolished", "") or song.get("lyrics_polished", "") or song.get("lyricsRaw", "") or song.get("lyrics_raw", "")).strip()
        if hasattr(self, "music_song_lyrics_editor"):
            self.music_song_lyrics_editor.setPlainText(lyrics)
        effects = self._music_effect_preview_from_creativity(int(settings.get("creativity", 55) or 55))
        for key, bar_name, label_name in (
            ("valence", "music_valence_bar", "music_valence_value"),
            ("danceability", "music_danceability_bar", "music_danceability_value"),
            ("instrumentalness", "music_instrumental_bar", "music_instrumental_value"),
        ):
            value = int(effects.get(key, 0) or 0)
            bar = getattr(self, bar_name, None)
            label = getattr(self, label_name, None)
            if bar is not None:
                bar.setValue(value)
                bar.setFormat(f"{value}%")
            if label is not None:
                label.setText(f"{value}%")

    def _refresh_music_settings_fields(self, settings: dict):
        """Delegate all settings UI population to the music settings coordinator."""
        self.music_settings_coordinator.populate_suno_settings_ui(settings)
        self.music_settings_coordinator.populate_performance_settings_ui(settings)
        self.music_settings_coordinator.populate_misc_settings_ui(settings)

        # Remaining image/perf fields not yet in coordinator
        bg_dir = str(settings.get("imageBackgroundSamplesDir", "")).strip()
        thumb_dir = str(settings.get("imageThumbnailSamplesDir", "")).strip()
        if hasattr(self, "music_settings_image_bg_samples_dir"):
            self.music_settings_image_bg_samples_dir.setText(bg_dir)
        if hasattr(self, "music_settings_image_thumb_samples_dir"):
            self.music_settings_image_thumb_samples_dir.setText(thumb_dir)
        if hasattr(self, "music_settings_image_output_dir"):
            self.music_settings_image_output_dir.setText(str(settings.get("imageOutputDir", "")).strip())
        if hasattr(self, "music_settings_image_resolution"):
            res = str(settings.get("outputResolution", "")).strip() or str(settings.get("imageResolution", "1920x1080")).strip() or "1920x1080"
            idx = self.music_settings_image_resolution.findData(res)
            self.music_settings_image_resolution.setCurrentIndex(idx if idx >= 0 else 0)
        if hasattr(self, "music_settings_style_strength"):
            strength = int(settings.get("styleStrength", 60) or 60)
            strength = max(0, min(100, strength))
            self.music_settings_style_strength.blockSignals(True)
            self.music_settings_style_strength.setValue(strength)
            self.music_settings_style_strength.blockSignals(False)
        if hasattr(self, "music_settings_style_strength_value"):
            self.music_settings_style_strength_value.setText(str(int(settings.get("styleStrength", 60) or 60)))
        if hasattr(self, "perf_music_workers_spin"):
            val = max(1, min(5, int(settings.get("perfMusicWorkers", 1) or 1)))
            self.perf_music_workers_spin.blockSignals(True)
            self.perf_music_workers_spin.setValue(val)
            self.perf_music_workers_spin.blockSignals(False)
        if hasattr(self, "perf_image_workers_spin"):
            val = max(1, min(8, int(settings.get("perfImageWorkers", 4) or 4)))
            self.perf_image_workers_spin.blockSignals(True)
            self.perf_image_workers_spin.setValue(val)
            self.perf_image_workers_spin.blockSignals(False)
        if hasattr(self, "music_pools_generate_count"):
            self.music_pools_generate_count.setText(str(getattr(self, "_music_pools_generate_count", 10000)))
        if hasattr(self, "music_pools_page_size_input"):
            self.music_pools_page_size_input.setText(str(int(getattr(self, "_music_pools_page_size", 100) or 100)))

    def _refresh_music_ui(self):
        if not hasattr(self, "music_history_table"):
            return
        settings = self._music_settings()
        self._music_ui_loading = True
        try:
            self._refresh_music_runtime_controls(settings)
            self._refresh_music_editor_state(settings)
            self._refresh_music_settings_fields(settings)
            self._music_controller.refresh_music_reference_views()
        finally:
            self._music_ui_loading = False
        self._update_music_credit_cost_label()

    def _on_music_show_all_history(self):
        self.music_history_from_date = ""
        self.music_history_to_date = ""
        self.music_last_batch_only = False
        self._persist_music_runtime_state()
        widget_factory.set_calendar_picker_value(getattr(self, "music_history_from_input", None), "")
        widget_factory.set_calendar_picker_value(getattr(self, "music_history_to_input", None), "")
        if hasattr(self, "music_history_last_batch"):
            self.music_history_last_batch.blockSignals(True)
            self.music_history_last_batch.setChecked(False)
            self.music_history_last_batch.blockSignals(False)
        self._refresh_music_history_table(force=True)

    def _music_effect_preview_from_creativity(self, creativity: int) -> dict[str, int]:
        c = max(0, min(100, int(creativity or 0)))
        return {
            "valence": int(min(95, max(5, 20 + c * 0.7))),
            "danceability": int(min(95, max(5, 15 + c * 0.75))),
            "instrumentalness": int(min(95, max(5, 10 + c * 0.55))),
        }

    @staticmethod
    def _music_pick_random(items: list[dict]) -> dict | None:
        return random.choice(items) if items else None

    @staticmethod
    def _music_pick_active_item(items: list[dict], active_ids: list[str]) -> dict | None:
        if not active_ids:
            return None
        pool = [row for row in items if str((row or {}).get("id", "")).strip() in active_ids]
        return MusicUiHandlersMixin._music_pick_random(pool)

    @staticmethod
    def _music_pick_from_pool_item(items: list[dict], enabled_ids: list[str]) -> dict | None:
        pool = [row for row in items if str((row or {}).get("id", "")).strip() in enabled_ids] if enabled_ids else list(items)
        return MusicUiHandlersMixin._music_pick_random(pool)

    def _resolve_music_generation_inputs(self, song_index: int) -> dict[str, str]:
        return self._music_coordinator.resolve_generation_inputs(song_index)

    def _music_settings(self) -> dict:
        settings = self.music_data.get("settings") if isinstance(self.music_data.get("settings"), dict) else {}
        return settings if isinstance(settings, dict) else {}

    def _save_music_app_data(self) -> None:
        self.music_data = normalize_music_app_data(self.music_data)
        self.e_settings = dict(self._music_settings())
        self._log(f"[{time.strftime('%H:%M:%S')}] Music app state kept in database memory")

    def _music_collection(self, kind: str) -> list[dict]:
        key = "descriptions" if str(kind).strip().lower().startswith("desc") else "structures"
        rows = self.music_data.get(key)
        return rows if isinstance(rows, list) else []

    def _music_text_widget_bundle(self, kind: str) -> tuple[object | None, object | None, object | None, object | None]:
        key = "descriptions" if str(kind).strip().lower().startswith("desc") else "structures"
        return (
            getattr(self, f"music_{key}_list", None),
            getattr(self, f"music_{key}_name", None),
            getattr(self, f"music_{key}_match_key", None),
            getattr(self, f"music_{key}_editor", None),
        )

    def _music_active_setting_key(self, kind: str) -> str:
        return "activeDescriptionIds" if str(kind).strip().lower().startswith("desc") else "activeStructureIds"

    def _music_active_ids(self, kind: str) -> list[str]:
        settings = self._music_settings()
        ids = settings.get(self._music_active_setting_key(kind))
        return [str(x).strip() for x in (ids or []) if str(x).strip()]

    def _set_music_status(self, text: str) -> None:
        message = str(text or "").strip() or "Ready"
        self._footer.set_music_status(message)
        self._footer.set_status(message)

    def _set_music_suno_status(self, text: str) -> None:
        message = str(text or "").strip()
        self._footer.set_suno_status(message)

    def _get_suno_api_base_url(self, settings: dict | None = None) -> str:
        s = settings if isinstance(settings, dict) else self._music_settings()
        base = str(s.get("sunoApiBaseUrl", "")).strip()
        return base or "https://api.sunoapi.org"

    def _trigger_music_suno_poll(self, *, manual: bool = False, max_tasks: int = 10) -> None:
        # Skip automatic polls when no generation is active — avoids wasted DB queries
        if not manual and not self._music_suno_auto_poll_enabled:
            return
        self._music_coordinator.trigger_suno_poll(manual=manual, max_tasks=max_tasks)

    def _update_music_settings(self, patch: dict) -> None:
        self._music_coordinator.update_settings(patch)
        self._update_music_credit_cost_label()

    def _update_music_credit_cost_label(self) -> None:
        """Recalculate and display the estimated Suno credit cost for current settings."""
        try:
            if not hasattr(self, "music_credit_cost_label"):
                return
            settings = self._music_settings()
            auto_suno = bool(settings.get("autoGSuno", False))
            lyrics_provider = str(settings.get("lyricsProvider", "")).strip() or str(settings.get("songDraftProvider", "deepseek")).strip() or "deepseek"

            # If neither Suno feature is active, hide cost
            if not auto_suno and lyrics_provider != "suno":
                self.music_credit_cost_label.setText("")
                return

            # Calculate total songs
            songs_per_batch = max(1, int(settings.get("defaultSongCount", 1) or 1))
            ok_ids = [x for x in list(settings.get("channelOkProfileIds") or []) if str(x).strip()]
            channel_count = max(1, len(ok_ids)) if ok_ids else 1

            # Date count
            date_list = self._music_coordinator._resolve_date_list()
            date_count = len(date_list) if date_list else 1

            total = date_count * channel_count * songs_per_batch

            # Credit costs
            cost_music = max(0, int(settings.get("sunoCreditsCostMusic", 5) or 0))
            cost_lyrics = max(0, int(settings.get("sunoCreditsCostLyrics", 1) or 0))

            suno_cost = 0
            parts = []
            if auto_suno:
                suno_cost += total * cost_music
                parts.append(f"Music: {total}×{cost_music}")
            if lyrics_provider == "suno":
                suno_cost += total * cost_lyrics
                parts.append(f"Lyrics: {total}×{cost_lyrics}")

            detail = " + ".join(parts)
            self.music_credit_cost_label.setText(f"⚡ {suno_cost} credits ({detail})")
        except Exception:
            pass

    def _apply_music_toggle_state(self, button: QPushButton | None, checked: bool) -> None:
        if button is None:
            return
        button.blockSignals(True)
        button.setChecked(bool(checked))
        self._sync_toggle_button(button, bool(checked))
        button.blockSignals(False)

    def _music_profile_by_id(self, profile_id: str) -> dict | None:
        return self.profile_mgmt_coordinator.music_profile_by_id(profile_id)

    def _resolve_music_suno_dirs(self, song: dict, *, create_missing: bool) -> dict[str, str]:
        """Thin delegation to MusicGenerationCoordinator.resolve_suno_dirs."""
        return self._music_coordinator.resolve_suno_dirs(
            self.db_cfg,
            self._music_profile_by_id,
            song,
            self._music_settings(),
            create_missing=create_missing,
        )

    def _set_music_clipboard(self, text: str, success_message: str) -> None:
        QApplication.clipboard().setText(str(text or ""))
        self._set_music_status(success_message)

    def _run_music_generation_worker(self, request: dict) -> None:
        self._music_coordinator.generate_music_batch(request)

    def _handle_song(self, event: dict) -> None:
        self._music_coordinator.handle_song_event(event)

    def _handle_lyrics_polished(self, event: dict) -> None:
        self._music_coordinator.handle_lyrics_polished_event(event)

    def _handle_suno_result(self, event: dict) -> None:
        message = str(event.get("message", "")).strip()
        if message:
            self._set_music_suno_status(message)
            self._set_music_status(message)

    def _handle_suno_poll_result(self, event: dict) -> None:
        self._music_coordinator.handle_suno_poll_result_event(event)

    def _handle_suno_schedule_poll(self, event: dict) -> None:
        self._music_coordinator.handle_suno_schedule_poll_event(event)

    def _set_music_settings_status(self, text: str) -> None:
        message = str(text or "").strip()
        if message:
            self._set_music_status(message)

    def _set_music_pools_status(self, text: str) -> None:
        message = str(text or "").strip()
        if message:
            self._set_music_status(message)

    def _music_db_cfg_from_forms(self) -> DbCfg | None:
        return self.db_cfg

    def _music_open_path(self, target_path: str) -> bool:
        path_text = str(target_path or "").strip()
        if not path_text:
            QMessageBox.warning(self, "Open Path", "Path is empty.")
            return False
        if not Path(path_text).exists():
            QMessageBox.warning(self, "Open Path", f"Path does not exist:\n{path_text}")
            return False
        os.startfile(path_text)
        return True

    def _music_browse_directory_into(self, line_edit: QLineEdit, title: str) -> None:
        current = str(line_edit.text() or "").strip()
        picked = QFileDialog.getExistingDirectory(self, title, current or os.getcwd())
        if picked:
            line_edit.setText(picked)

    def _music_browse_file_into(self, line_edit: QLineEdit, title: str, filter_text: str) -> None:
        current = str(line_edit.text() or "").strip()
        picked, _ = QFileDialog.getOpenFileName(self, title, current or "", filter_text)
        if picked:
            line_edit.setText(picked)

    def _music_apply_settings_patch(self, patch: dict, success_message: str) -> None:
        if not patch:
            return
        self._apply_settings_patch_to_database(patch)
        self._refresh_music_ui()
        self._set_music_settings_status(success_message)
        self._set_music_status(success_message)

    def _set_music_profiles(self, rows: list[dict]) -> None:
        self.music_data["profiles"] = rows

    def _selected_music_settings_profile(self) -> dict | None:
        return self.profile_coordinator.selected_profile()

    def _load_music_settings_profile_details(self) -> None:
        return self.profile_mgmt_coordinator.load_profile_details()

    def _create_music_settings_profile(self) -> None:
        return self.profile_mgmt_coordinator.create_profile()

    def _save_music_settings_profile(self) -> None:
        return self.profile_coordinator.save_profile()

    def _save_music_settings_profile_impl(self) -> None:
        return self.profile_mgmt_coordinator.save_profile_details()

    def _delete_music_settings_profile(self) -> None:
        return self.profile_mgmt_coordinator.delete_profile()

    def _music_current_pool_kind(self) -> str:
        return self.music_settings_coordinator.music_current_pool_kind()
