"""Auto-extracted UI handler methods from MainWindow."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize, QDate, QTimer
from PyQt6.QtWidgets import (
    QLabel, QMenu, QListWidgetItem, QTableWidgetItem,
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSizePolicy,
    QComboBox, QLineEdit, QTextEdit, QMessageBox, QHeaderView,
    QTableWidget, QDialog,
)
from PyQt6.QtGui import QColor, QPixmap

from ..database.image_db import list_prompt_presets
from ..services.image_generation import list_images_in_folder
from ..views.helpers import widget_factory
from ..views.helpers.style_helper import render_svg_icon


from ..views.preset_manager_dialog import PresetManagerDialog
from ..features.text_presets.coordinator import TextPresetManagerCoordinator

class ImageUiHandlersMixin:
    """Mixin providing UI interaction handlers extracted from MainWindow."""

    def _refresh_image_ui(self, force: bool = False):
        if not hasattr(self, "image_jobs_table"):
            return
        if getattr(self, "_current_primary_page", "") != "image" and not force:
            setattr(self, "_image_dirty", True)
            return
        setattr(self, "_image_dirty", False)
        settings = self._music_settings()
        self._image_ui_loading = True
        try:
            if not str(self.image_from_date or "").strip() or not str(self.image_to_date or "").strip():
                today = QDate.currentDate().toString("yyyy-MM-dd")
                self.image_from_date = today
                self.image_to_date = today
            widget_factory.set_calendar_picker_value(getattr(self, "image_from_input", None), self.image_from_date)
            widget_factory.set_calendar_picker_value(getattr(self, "image_to_input", None), self.image_to_date)
            if hasattr(self, "image_prompt_editor") and not self.image_prompt_editor.hasFocus():
                if not self._image_prompt_text:
                    self._image_prompt_text = str(settings.get("imagePrompt", "")).strip()
                self.image_prompt_editor.blockSignals(True)
                self.image_prompt_editor.setPlainText(self._image_prompt_text)
                self.image_prompt_editor.blockSignals(False)
            self._refresh_image_prompt_presets()
            self._refresh_image_sample_lists()
            self._refresh_image_batches_list()
            self._refresh_image_jobs_table()
            self._set_image_status(self._image_status_message)
        finally:
            self._image_ui_loading = False

    def _refresh_image_prompt_presets(self):
        if not hasattr(self, "image_prompt_preset_combo"):
            return
        combo = self.image_prompt_preset_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Preset prompts...", userData="")
        if self.db_cfg:
            try:
                presets = list_prompt_presets(self.db_cfg, kind="background")
            except Exception:
                presets = []
            for row in presets:
                name = str(row.get("name", "")).strip()
                prompt = str(row.get("prompt", "")).strip()
                if not name or not prompt:
                    continue
                combo.addItem(name, userData=prompt)
        combo.blockSignals(False)

    def _refresh_image_sample_lists(self):
        settings = self._music_settings()
        bg_dir, thumb_dir = self._resolve_image_sample_dirs(settings)
        bg_random = bool(settings.get("imageBgRandom", False))
        thumb_random = bool(settings.get("imageThumbRandom", False))
        bg_selected = {str(x).strip() for x in list(settings.get("imageBgSamples") or []) if str(x).strip()}
        thumb_selected = {str(x).strip() for x in list(settings.get("imageThumbSamples") or []) if str(x).strip()}
        bg_rows = list_images_in_folder(bg_dir)
        thumb_rows = list_images_in_folder(thumb_dir)
        if hasattr(self, "image_bg_random_checkbox"):
            self.image_bg_random_checkbox.blockSignals(True)
            self.image_bg_random_checkbox.setChecked(bool(bg_random))
            self.image_bg_random_checkbox.blockSignals(False)
        if hasattr(self, "image_thumb_random_checkbox"):
            self.image_thumb_random_checkbox.blockSignals(True)
            self.image_thumb_random_checkbox.setChecked(bool(thumb_random))
            self.image_thumb_random_checkbox.blockSignals(False)
        if hasattr(self, "image_bg_samples_folder_label"):
            if not bg_dir:
                self.image_bg_samples_folder_label.setText("Folder: (not set)")
            elif not Path(bg_dir).exists():
                self.image_bg_samples_folder_label.setText(f"Folder missing: {bg_dir}")
            else:
                suffix = " · Random: ON" if bg_random else f" · Selected: {min(5, len(bg_selected))}/5"
                self.image_bg_samples_folder_label.setText(f"Folder: {bg_dir} · {len(bg_rows)} images{suffix}")
        if hasattr(self, "image_thumb_samples_folder_label"):
            if not thumb_dir:
                self.image_thumb_samples_folder_label.setText("Folder: (not set)")
            elif not Path(thumb_dir).exists():
                self.image_thumb_samples_folder_label.setText(f"Folder missing: {thumb_dir}")
            else:
                suffix = " · Random: ON" if thumb_random else f" · Selected: {min(5, len(thumb_selected))}/5"
                self.image_thumb_samples_folder_label.setText(f"Folder: {thumb_dir} · {len(thumb_rows)} images{suffix}")
        if hasattr(self, "image_bg_samples_empty_label"):
            self.image_bg_samples_empty_label.setVisible(len(bg_rows) == 0)
        if hasattr(self, "image_thumb_samples_empty_label"):
            self.image_thumb_samples_empty_label.setVisible(len(thumb_rows) == 0)
        if hasattr(self, "image_bg_samples_list"):
            widget = self.image_bg_samples_list
            widget.blockSignals(True)
            widget.setEnabled(not bg_random)
            widget.clear()
            for row in bg_rows:
                path = str(row.get("filePath", "")).strip()
                name = str(row.get("fileName", "")).strip() or path
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                widget.addItem(item)
                if path in bg_selected:
                    item.setSelected(True)
            if bg_random:
                widget.clearSelection()
            widget.blockSignals(False)
        if hasattr(self, "image_thumb_samples_list"):
            widget = self.image_thumb_samples_list
            widget.blockSignals(True)
            widget.setEnabled(not thumb_random)
            widget.clear()
            for row in thumb_rows:
                path = str(row.get("filePath", "")).strip()
                name = str(row.get("fileName", "")).strip() or path
                item = QListWidgetItem(name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                widget.addItem(item)
                if path in thumb_selected:
                    item.setSelected(True)
            if thumb_random:
                widget.clearSelection()
            widget.blockSignals(False)
        table = getattr(self, "image_jobs_table", None)
        has_sel = False
        try:
            if table is not None and table.selectionModel() is not None:
                has_sel = bool(table.selectionModel().selectedRows())
        except Exception:
            has_sel = False
        if not has_sel:
            self._reset_image_previews()

    def _refresh_image_batches_list(self):
        if not hasattr(self, "image_batches_list"):
            return
        widget = self.image_batches_list
        widget.blockSignals(True)
        try:
            selected_ids = {str(item.data(Qt.ItemDataRole.UserRole).get("batchId", "")).strip() for item in widget.selectedItems() if isinstance(item.data(Qt.ItemDataRole.UserRole), dict)}
        except Exception:
            selected_ids = set()
        widget.clear()
        rows: list[dict] = []
        if self.db_cfg:
            try:
                from ..database.music_db import list_batches_for_history

                rows = list_batches_for_history(self.db_cfg, from_ymd=str(self.image_from_date or "").strip(), to_ymd=str(self.image_to_date or "").strip(), limit=800)
            except Exception:
                rows = []
        profiles = {str((p or {}).get("id", "")).strip(): dict(p) for p in (self.music_data.get("profiles") or []) if isinstance(p, dict)}
        for row in rows:
            batch_id = str(row.get("batchId", "")).strip()
            if not batch_id:
                continue
            min_created = str(row.get("minCreatedAt", "")).strip()
            run_date = min_created[:10] if min_created else ""
            ok_id = str(row.get("profileOkId", "")).strip()
            alt_id = str(row.get("profileAltId", "")).strip()
            ok_name = str((profiles.get(ok_id, {}) or {}).get("name", ok_id)).strip()
            alt_name = str((profiles.get(alt_id, {}) or {}).get("name", alt_id)).strip()
            label = f"{run_date} · {ok_name} / {alt_name} · {batch_id}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row)
            widget.addItem(item)
            if batch_id in selected_ids:
                item.setSelected(True)
        widget.blockSignals(False)
        self._sync_image_batches_selected_label()

    def _set_image_preview(self, label: QLabel | None, path_text: str) -> None:
        if label is None:
            return
        p = str(path_text or "").strip()
        if not p or not Path(p).exists():
            label.setPixmap(QPixmap())
            label.setText("Select a job from Job Queue to preview")
            return
        px = QPixmap(p)
        if px.isNull():
            label.setPixmap(QPixmap())
            label.setText("Select a job from Job Queue to preview")
            return
        w = int(label.width() or 0)
        h = int(label.height() or 0)
        if w <= 8 or h <= 8:
            w, h = (640, 360)
        scaled = px.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        if scaled.width() > w or scaled.height() > h:
            x = max(0, int((scaled.width() - w) / 2))
            y = max(0, int((scaled.height() - h) / 2))
            scaled = scaled.copy(x, y, w, h)
        label.setText("")
        label.setPixmap(scaled)

    def _on_image_bg_random_toggled(self, checked: bool):
        widget = getattr(self, "image_bg_samples_list", None)
        if widget is not None:
            widget.blockSignals(True)
            widget.clearSelection()
            widget.blockSignals(False)
        patch = {"imageBgRandom": bool(checked)}
        if bool(checked):
            patch["imageBgSamples"] = []
        self._update_music_settings(patch)
        self._refresh_image_sample_lists()

    def _on_image_thumb_random_toggled(self, checked: bool):
        widget = getattr(self, "image_thumb_samples_list", None)
        if widget is not None:
            widget.blockSignals(True)
            widget.clearSelection()
            widget.blockSignals(False)
        patch = {"imageThumbRandom": bool(checked)}
        if bool(checked):
            patch["imageThumbSamples"] = []
        self._update_music_settings(patch)
        self._refresh_image_sample_lists()

    def _refresh_image_jobs_table(self):
        if not hasattr(self, "image_jobs_table"):
            return
        from_text = str(self.image_from_date or "").strip()
        to_text = str(self.image_to_date or "").strip()
        grouped_rows, has_pending = self._image_coordinator.group_jobs_for_ui(from_ymd=from_text, to_ymd=to_text, limit=5000) if self._image_coordinator else ([], False)
        _cache = getattr(self, "_svg_icon_cache", None)
        if _cache is None:
            _cache = {}
            self._svg_icon_cache = _cache
        retry_icon = render_svg_icon(self._lucide_icon_path("rotate-cw"), 14, self.ui["text"], cache=_cache)

        def _build_image_status_cell(*, color: str, tooltip: str, enabled: bool, on_retry):
            host = QWidget()
            layout = QHBoxLayout(host)
            layout.setContentsMargins(4, 2, 4, 2)
            layout.setSpacing(6)
            dot = QLabel()
            dot.setToolTip(tooltip)
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 7px;")
            layout.addWidget(dot, 0)
            layout.addStretch(1)
            btn = QPushButton()
            self._set_button_role(btn, "tableIcon")
            btn.setFixedSize(22, 22)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.setToolTip("Retry")
            btn.setIcon(retry_icon)
            btn.setIconSize(QSize(14, 14))
            btn.setEnabled(bool(enabled))
            btn.clicked.connect(on_retry)
            layout.addWidget(btn, 0)
            layout.setAlignment(btn, Qt.AlignmentFlag.AlignVCenter)
            return host

        if hasattr(self, "image_jobs_empty_label"):
            self.image_jobs_empty_label.setVisible(len(grouped_rows) == 0)
        if hasattr(self, "image_stop_button"):
            self.image_stop_button.setEnabled(bool(has_pending or getattr(self, "_image_poll_running", False)))
        if hasattr(self, "image_generate_now_button"):
            self.image_generate_now_button.setEnabled(not bool(getattr(self, "_image_poll_running", False)))
        if hasattr(self, "image_clear_queue_button"):
            self.image_clear_queue_button.setEnabled(not bool(getattr(self, "_image_poll_running", False)))

        row_layout = self._image_coordinator.compute_row_spans(grouped_rows) if self._image_coordinator else []
        row_data_list = self._image_coordinator.build_image_job_rows(grouped_rows, self.ui) if self._image_coordinator else []

        table = self.image_jobs_table
        table.setUpdatesEnabled(False)
        try:
            table.clearContents()
            table.setRowCount(0)
            row_index = 0
            data_index = 0
            for layout_info in row_layout:
                if layout_info["type"] == "header":
                    table.insertRow(row_index)
                    item = QTableWidgetItem(f"{layout_info['batchId']} · {layout_info['runDate']}")
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    item.setBackground(QColor(self.ui["primary_pressed"]))
                    item.setForeground(QColor("#ffffff"))
                    table.setItem(row_index, 0, item)
                    table.setSpan(row_index, 0, 1, table.columnCount())
                    row_index += 1
                else:
                    table.insertRow(row_index)
                    rd = row_data_list[data_index]
                    data_index += 1
                    row_meta = rd["row_meta"]
                    table.setItem(row_index, 0, QTableWidgetItem(""))
                    table.setItem(row_index, 1, QTableWidgetItem(rd["profile_name"]))
                    table.setItem(row_index, 2, QTableWidgetItem(rd["role"]))
                    bg_item = QTableWidgetItem("")
                    bg_item.setData(Qt.ItemDataRole.UserRole, {"jobUid": rd["bg_uid"], "row": row_meta})
                    table.setItem(row_index, 3, bg_item)
                    table.setCellWidget(
                        row_index,
                        3,
                        _build_image_status_cell(
                            color=rd["bg_color"],
                            tooltip=rd["bg_tip"],
                            enabled=bool(self._image_coordinator) and rd["bg_enabled"],
                            on_retry=lambda _=False, a=rd["bg_uid"], b=rd["th_uid"]: self._on_image_retry_bg_clicked(a, b),
                        ),
                    )
                    th_item = QTableWidgetItem("")
                    th_item.setData(Qt.ItemDataRole.UserRole, {"jobUid": rd["th_uid"], "row": row_meta})
                    table.setItem(row_index, 4, th_item)
                    table.setCellWidget(
                        row_index,
                        4,
                        _build_image_status_cell(
                            color=rd["th_color"],
                            tooltip=rd["th_tip"],
                            enabled=bool(self._image_coordinator) and rd["th_enabled"],
                            on_retry=lambda _=False, a=rd["th_uid"], b=row_meta["batchId"], c=row_meta["profileId"]: self._on_image_retry_th_clicked(a, b, c),
                        ),
                    )
                    bg_file_item = QTableWidgetItem(rd["bg_out"])
                    bg_file_item.setData(Qt.ItemDataRole.UserRole, {"jobUid": rd["bg_uid"], "row": row_meta})
                    table.setItem(row_index, 5, bg_file_item)
                    th_file_item = QTableWidgetItem(rd["th_out"])
                    th_file_item.setData(Qt.ItemDataRole.UserRole, {"jobUid": rd["th_uid"], "row": row_meta})
                    table.setItem(row_index, 6, th_file_item)
                    row_index += 1
        finally:
            table.setUpdatesEnabled(True)

    def _on_image_retry_bg_clicked(self, bg_uid: str, th_uid: str) -> None:
        if not self._image_coordinator:
            return
        uids = [str(bg_uid or "").strip()]
        tuid = str(th_uid or "").strip()
        if tuid:
            uids.append(tuid)
        uids = [x for x in uids if x]
        if not uids:
            return
        self._image_coordinator.retry_jobs(uids)
        self._set_image_status("Retrying background (and thumbnail)...")

    def _on_image_retry_th_clicked(self, th_uid: str, batch_id: str = "", profile_id: str = "") -> None:
        if not self._image_coordinator:
            return
        uid = str(th_uid or "").strip()
        if uid:
            self._image_coordinator.retry_jobs([uid])
            self._set_image_status("Retrying thumbnail...")
        else:
            # No thumbnail job exists yet - create it
            result = self._image_coordinator.enqueue_thumbnail_for_batch(batch_id, profile_id)
            if bool(result.get("ok", False)):
                self._set_image_status("Enqueued thumbnail job...")
            else:
                QMessageBox.warning(self, "Image", str(result.get("message", "Failed to enqueue thumbnail")))
            self._refresh_image_jobs_table()

    def _on_image_bg_selection_changed(self):
        if getattr(self, "_image_ui_loading", False):
            return
        widget = getattr(self, "image_bg_samples_list", None)
        if widget is None:
            return
        selected = [str(item.data(Qt.ItemDataRole.UserRole) or "").strip() for item in widget.selectedItems()]
        selected = [x for x in selected if x]
        if len(selected) > 5:
            for item in widget.selectedItems()[5:]:
                item.setSelected(False)
            QMessageBox.warning(self, "Image", "Background samples selection is limited to 5.")
            selected = [str(item.data(Qt.ItemDataRole.UserRole) or "").strip() for item in widget.selectedItems()]
            selected = [x for x in selected if x]
        self._update_music_settings({"imageBgSamples": selected})

    def _on_image_thumb_selection_changed(self):
        if getattr(self, "_image_ui_loading", False):
            return
        widget = getattr(self, "image_thumb_samples_list", None)
        if widget is None:
            return
        selected = [str(item.data(Qt.ItemDataRole.UserRole) or "").strip() for item in widget.selectedItems()]
        selected = [x for x in selected if x]
        if len(selected) > 5:
            for item in widget.selectedItems()[5:]:
                item.setSelected(False)
            QMessageBox.warning(self, "Image", "Thumbnail samples selection is limited to 5.")
            selected = [str(item.data(Qt.ItemDataRole.UserRole) or "").strip() for item in widget.selectedItems()]
            selected = [x for x in selected if x]
        self._update_music_settings({"imageThumbSamples": selected})

    def _on_image_prompt_preset_selected(self):
        if getattr(self, "_image_ui_loading", False):
            return
        if not hasattr(self, "image_prompt_preset_combo"):
            return
        prompt = str(self.image_prompt_preset_combo.currentData() or "").strip()
        if not prompt:
            return
        self._image_prompt_text = prompt
        if hasattr(self, "image_prompt_editor"):
            self.image_prompt_editor.blockSignals(True)
            self.image_prompt_editor.setPlainText(prompt)
            self.image_prompt_editor.blockSignals(False)
        self._update_music_settings({"imagePrompt": prompt})

    def _on_image_pick_prompt_clicked(self):
        if not self.db_cfg:
            QMessageBox.warning(self, "Image", "Postgres is not configured.")
            return
        picked = None
        try:
            from ..database.image_db import pick_least_used_preset
            picked = pick_least_used_preset(self.db_cfg, kind="background")
        except Exception:
            picked = None
        prompt = str((picked or {}).get("prompt", "")).strip()
        if prompt:
            self._image_prompt_text = prompt
            if hasattr(self, "image_prompt_editor"):
                self.image_prompt_editor.blockSignals(True)
                self.image_prompt_editor.setPlainText(prompt)
                self.image_prompt_editor.blockSignals(False)
            self._update_music_settings({"imagePrompt": prompt})

    def _on_image_manage_prompts_clicked(self):
        if not self.db_cfg:
            QMessageBox.warning(self, "Image", "Postgres is not configured.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Image Prompts")
        dlg.setMinimumWidth(860)
        root = QVBoxLayout(dlg)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        kind_combo = QComboBox()
        self._apply_card_field(kind_combo)
        kind_combo.addItem("Background", userData="background")
        kind_combo.addItem("Thumbnail", userData="thumbnail")
        header.addWidget(kind_combo, 0)
        header.addStretch(1)
        root.addLayout(header)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Name", "Used", "ID"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnHidden(2, True)
        self._apply_card_field(table)
        root.addWidget(table, 1)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        name_input = QLineEdit()
        self._apply_card_field(name_input)
        widget_factory.add_form_row(form, "Name", name_input, self.ui, apply_card_field=False, label_min_width=80)
        prompt_editor = QTextEdit()
        self._set_field_role(prompt_editor, "card")
        prompt_editor.setMinimumHeight(140)
        form.addWidget(prompt_editor)
        root.addLayout(form)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        btn_add = QPushButton("Add New")
        self._set_button_role(btn_add, "secondary")
        actions.addWidget(btn_add)
        btn_save = QPushButton("Save")
        self._set_button_role(btn_save, "primary")
        actions.addWidget(btn_save)
        btn_delete = QPushButton("Delete")
        self._set_button_role(btn_delete, "danger")
        actions.addWidget(btn_delete)
        actions.addStretch(1)
        btn_close = QPushButton("Close")
        self._set_button_role(btn_close, "secondary")
        actions.addWidget(btn_close)
        root.addLayout(actions)

        state = {"id": None}
        co = self.image_prompt_preset_coordinator

        def _populate_table(rows: list[dict], select_id: int | None):
            """Populate the table widget from a list of preset rows."""
            table.setUpdatesEnabled(False)
            try:
                table.setRowCount(0)
                for row in rows:
                    r = table.rowCount()
                    table.insertRow(r)
                    table.setItem(r, 0, QTableWidgetItem(str(row.get("name", "")).strip()))
                    table.setItem(r, 1, QTableWidgetItem(str(int(row.get("usedCount", 0) or 0))))
                    id_item = QTableWidgetItem(str(int(row.get("id", 0) or 0)))
                    id_item.setData(Qt.ItemDataRole.UserRole, int(row.get("id", 0) or 0))
                    table.setItem(r, 2, id_item)
                    if select_id is not None and int(row.get("id", 0) or 0) == int(select_id):
                        table.selectRow(r)
            finally:
                table.setUpdatesEnabled(True)

        def reload_table(select_id: int | None = None):
            kind = str(kind_combo.currentData() or "background")
            rows = co.list_presets(kind=kind)
            _populate_table(rows, select_id)

        def clear_form():
            state["id"] = None
            name_input.setText("")
            prompt_editor.setPlainText("")

        def load_selected():
            rows = table.selectionModel().selectedRows()
            if not rows:
                return
            r = int(rows[0].row())
            id_item = table.item(r, 2)
            preset_id = int(id_item.data(Qt.ItemDataRole.UserRole) or 0) if id_item is not None else 0
            if preset_id <= 0:
                return
            kind = str(kind_combo.currentData() or "background")
            current = co.load_preset(kind=kind, preset_id=preset_id)
            if not current:
                return
            state["id"] = preset_id
            name_input.setText(str(current.get("name", "")).strip())
            prompt_editor.setPlainText(str(current.get("prompt", "")).strip())

        def on_add():
            clear_form()
            name_input.setFocus()

        def on_save():
            kind = str(kind_combo.currentData() or "background")
            try:
                saved = co.save_preset(
                    preset_id=state["id"],
                    kind=kind,
                    name=str(name_input.text() or "").strip(),
                    prompt=str(prompt_editor.toPlainText() or "").strip(),
                )
                state["id"] = int(saved.get("id", 0) or 0) or None
                reload_table(select_id=state["id"])
            except Exception as exc:
                QMessageBox.warning(self, "Image", str(exc))

        def on_delete():
            pid = int(state.get("id") or 0)
            if pid <= 0:
                return
            if QMessageBox.question(self, "Image", "Delete this prompt preset?") != QMessageBox.StandardButton.Yes:
                return
            try:
                co.delete_preset(pid)
                clear_form()
                reload_table()
            except Exception as exc:
                QMessageBox.warning(self, "Image", str(exc))

        btn_add.clicked.connect(on_add)
        btn_save.clicked.connect(on_save)
        btn_delete.clicked.connect(on_delete)
        btn_close.clicked.connect(lambda: dlg.close())
        table.itemSelectionChanged.connect(load_selected)
        kind_combo.currentIndexChanged.connect(lambda _: (clear_form(), reload_table()))

        clear_form()
        reload_table()
        dlg.exec()
        self._refresh_image_prompt_presets()

    def _on_image_generate_now_clicked(self):
        settings = self._music_settings()
        bg_dir, thumb_dir = self._resolve_image_sample_dirs(settings)
        batch_rows = self._get_selected_image_batches()
        result = self._image_coordinator.on_generate_now_clicked(
            batch_rows=batch_rows,
            prompt=str(self._image_prompt_text or "").strip(),
            bg_samples=[str(x).strip() for x in list(settings.get("imageBgSamples") or []) if str(x).strip()],
            thumb_samples=[str(x).strip() for x in list(settings.get("imageThumbSamples") or []) if str(x).strip()],
            bg_random=bool(settings.get("imageBgRandom", False)),
            thumb_random=bool(settings.get("imageThumbRandom", False)),
            bg_dir=bg_dir,
            thumb_dir=thumb_dir,
        )
        if result.get("warning"):
            QMessageBox.warning(self, "Image", result["warning"])
        if result.get("ok"):
            self._refresh_image_jobs_table()

    def _on_image_clear_queue_clicked(self):
        if not self.db_cfg:
            QMessageBox.warning(self, "Image", "Postgres is not configured.")
            return
        if QMessageBox.question(self, "Image", "Delete ALL image jobs from Postgres?") != QMessageBox.StandardButton.Yes:
            return
        self._image_cancel_requested = True
        try:
            from ..database.image_db import clear_all_image_jobs

            clear_all_image_jobs(self.db_cfg)
        except Exception as exc:
            QMessageBox.warning(self, "Image", f"Failed to clear job queue: {exc}")
            return
        finally:
            self._image_cancel_requested = False
        self._set_image_status("Cleared job queue")
        self._reset_image_previews()
        self._refresh_image_ui(force=True)

    def _on_image_job_selected(self):
        if not hasattr(self, "image_jobs_table"):
            return
        table = self.image_jobs_table
        rows = table.selectionModel().selectedRows()
        if not rows:
            if hasattr(self, "image_footer_detail"):
                self.image_footer_detail.setText("")
            self._reset_image_previews()
            return
        r = int(rows[0].row())
        meta = None
        for c in (3, 4, 5, 6):
            it = table.item(r, c)
            if it is None:
                continue
            data = it.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                meta = data
                break
        detail = ""
        if self.db_cfg and isinstance(meta, dict):
            try:
                from ..database.image_db import get_image_job_by_uid
                bg_uid = str((meta.get("row") or {}).get("bgUid", "")).strip() if isinstance(meta.get("row"), dict) else str(meta.get("jobUid", "")).strip()
                th_uid = str((meta.get("row") or {}).get("thUid", "")).strip() if isinstance(meta.get("row"), dict) else ""
                bg = get_image_job_by_uid(self.db_cfg, bg_uid) if bg_uid else None
                th = get_image_job_by_uid(self.db_cfg, th_uid) if th_uid else None
                bg_status = str((bg or {}).get("status", "")).strip().upper()
                th_status = str((th or {}).get("status", "")).strip().upper()
                bg_out = str((bg or {}).get("outputImagePath", "")).strip() if bg_status == "READY" else ""
                th_out = str((th or {}).get("outputImagePath", "")).strip() if th_status == "READY" else ""
                self._set_image_preview(getattr(self, "image_bg_preview", None), bg_out)
                self._set_image_preview(getattr(self, "image_thumb_preview", None), th_out)
                bg_err = str((bg or {}).get("error", "")).strip()
                th_err = str((th or {}).get("error", "")).strip()
                detail = bg_err or th_err or bg_out or th_out
            except Exception:
                detail = ""
        if hasattr(self, "image_footer_detail"):
            self.image_footer_detail.setText(detail)

    def _on_image_job_double_clicked(self, row: int, column: int):
        if not hasattr(self, "image_jobs_table"):
            return
        table = self.image_jobs_table
        item = table.item(int(row), int(column))
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        uid = ""
        if isinstance(data, dict):
            uid = str(data.get("jobUid", "")).strip()
            if isinstance(data.get("row"), dict):
                if int(column) in (3, 5):
                    uid = str(data["row"].get("bgUid", "")).strip()
                elif int(column) in (4, 6):
                    uid = str(data["row"].get("thUid", "")).strip()
        if not uid or not self.db_cfg:
            return
        try:
            from ..database.image_db import get_image_job_by_uid
            job = get_image_job_by_uid(self.db_cfg, uid) or {}
            status = str(job.get("status", "")).strip().upper()
            out_path = str(job.get("outputImagePath", "")).strip()
            if status == "FAILED":
                self._image_coordinator.retry_job(uid)
                self._set_image_status("Retrying image job...")
                return
            if status in ("PENDING", "RUNNING"):
                self._set_image_status(f"Job is already {status.lower()}...")
                return
            if status == "READY" and out_path and Path(out_path).exists():
                self._music_open_path(out_path)
                return
        except Exception:
            return

    def _handle_image_poll_result(self, event: dict):
        self._image_poll_running = False
        self._image_coordinator.stop_live_refresh()
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        manual = bool(event.get("manual", False))
        cancelled = bool(result.get("cancelled", False))

        summary = self._image_coordinator.process_poll_result(result, manual=manual, cancelled=cancelled)

        if cancelled:
            self._image_cancel_requested = False

        self._apply_image_poll_summary(summary, manual=manual)

    def _apply_image_poll_summary(self, summary: dict, *, manual: bool = False):
        """Apply the poll result summary to UI elements (labels, table refresh, auto-poll)."""
        if not summary["ok"]:
            self._set_image_status(summary["message"])
            if manual or self._current_primary_page == "image":
                if hasattr(self, "image_jobs_status_label"):
                    self.image_jobs_status_label.setText(summary["message"])
            return

        if hasattr(self, "image_jobs_status_label") and summary["message"]:
            self.image_jobs_status_label.setText(summary["message"])
        if summary["message"] and summary["checked"] > 0:
            self._set_image_status(summary["message"])

        if self._current_primary_page == "image":
            self._refresh_image_jobs_table()
        else:
            setattr(self, "_image_dirty", True)

        if summary["should_auto_poll"]:
            QTimer.singleShot(1500, lambda: self._image_coordinator.trigger_image_poll(manual=True, max_jobs=8))

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

    def _sync_image_auto_poll_timer(self) -> None:
        """Sync image auto-poll timer via TimerRegistry."""
        self._image_coordinator.sync_auto_poll_timer()

    def _sync_image_batches_selected_label(self) -> None:
        if not hasattr(self, "image_batches_selected_label") or not hasattr(self, "image_batches_list"):
            return
        count = 0
        try:
            count = len(self.image_batches_list.selectedItems())
        except Exception:
            count = 0
        self.image_batches_selected_label.setText(f"Selected: {count}")

    def _on_image_batches_selection_changed(self) -> None:
        if getattr(self, "_image_ui_loading", False):
            return
        self._sync_image_batches_selected_label()

    def _resolve_image_sample_dirs(self, settings: dict) -> tuple[str, str]:
        bg_dir = str((settings or {}).get("imageBackgroundSamplesDir", "")).strip()
        thumb_dir = str((settings or {}).get("imageThumbnailSamplesDir", "")).strip()
        if (not bg_dir or not thumb_dir) and str((settings or {}).get("imageSamplesDir", "")).strip():
            base = str((settings or {}).get("imageSamplesDir", "")).strip()
            if not bg_dir:
                bg_dir = str(Path(base) / "background")
            if not thumb_dir:
                thumb_dir = str(Path(base) / "thumbnail")
        return (bg_dir, thumb_dir)

    def _reset_image_previews(self) -> None:
        self._set_image_preview(getattr(self, "image_bg_preview", None), "")
        self._set_image_preview(getattr(self, "image_thumb_preview", None), "")

    def _on_image_open_bg_samples_dir(self) -> None:
        settings = self._music_settings()
        bg_dir, _ = self._resolve_image_sample_dirs(settings)
        if bg_dir:
            self._music_open_path(bg_dir)

    def _on_image_open_thumb_samples_dir(self) -> None:
        settings = self._music_settings()
        _, thumb_dir = self._resolve_image_sample_dirs(settings)
        if thumb_dir:
            self._music_open_path(thumb_dir)

    def _on_image_text_presets_clicked(self) -> None:
        """Open the Text Style Presets manager dialog."""
        coordinator = TextPresetManagerCoordinator(host=self, db_cfg=self.db_cfg)
        dlg = PresetManagerDialog(parent=self, coordinator=coordinator)
        dlg.exec()

    def _on_image_bg_sample_double_clicked(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._set_image_preview(getattr(self, "image_bg_preview", None), path)

    def _on_image_thumb_sample_double_clicked(self, item: QListWidgetItem) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._set_image_preview(getattr(self, "image_thumb_preview", None), path)

    def _on_image_prompt_changed(self) -> None:
        if getattr(self, "_image_ui_loading", False):
            return
        if not hasattr(self, "image_prompt_editor"):
            return
        self._image_prompt_text = str(self.image_prompt_editor.toPlainText() or "").strip()
        if getattr(self, "_image_prompt_persist_scheduled", False):
            return
        self._image_prompt_persist_scheduled = True
        QTimer.singleShot(350, lambda: self._flush_image_prompt_to_settings())

    def _flush_image_prompt_to_settings(self) -> None:
        self._image_prompt_persist_scheduled = False
        if self._image_ui_loading:
            return
        self._update_music_settings({"imagePrompt": str(self._image_prompt_text or "").strip()})

    def _on_image_date_changed(self) -> None:
        if getattr(self, "_image_ui_loading", False):
            return
        self.image_from_date = widget_factory.calendar_picker_value(self.image_from_input)
        self.image_to_date = widget_factory.calendar_picker_value(self.image_to_input)
        self._refresh_image_batches_list()
        self._refresh_image_jobs_table()

    def _get_selected_image_batches(self) -> list[dict]:
        """Gather selected batch rows from the image batches list widget."""
        rows: list[dict] = []
        if hasattr(self, "image_batches_list"):
            for item in self.image_batches_list.selectedItems():
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and str(data.get("batchId", "")).strip():
                    rows.append(data)
        return rows

    def _on_image_generate_thumbnails_clicked(self) -> None:
        result = self._image_coordinator.on_generate_thumbnails_clicked()
        if result.get("warning"):
            QMessageBox.warning(self, "Image", result["warning"])
        elif result.get("info"):
            QMessageBox.information(self, "Image", result["info"])
        if result.get("ok"):
            self._refresh_image_jobs_table()

    def _on_image_stop_clicked(self) -> None:
        self._image_cancel_requested = True
        self._set_image_status("Stopping image jobs...")
