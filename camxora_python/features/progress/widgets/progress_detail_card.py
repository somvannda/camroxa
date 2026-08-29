"""Selected progress row inspector — compact pipeline detail for CAMXORA Progress."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.icons import apply_button_icon, icon_label, section_heading
from features.create.widgets.studio_panel import NestedPanel, StudioPanel
from features.progress.widgets.operational_rows_card import EffectiveProgressRow
from shared.lib.formatting import format_channel_role_label
from shared.lib.manual_asset_paths import ManualAssetInspection, manual_inspection_key
from shared.lib.progress_presentation import (
    format_album_label,
    format_pipeline_step_text,
    format_run_date_label,
    format_youtube_compact,
    resolve_progress_error_message,
)


def _status_tone(status: str) -> str:
    key = str(status or "").strip().lower()
    if not key or key in {"—", "-", "not started"}:
        return "muted"
    if any(token in key for token in ("error", "fail", "blocked")):
        return "danger"
    if any(token in key for token in ("pending", "queued", "waiting")):
        return "warning"
    if any(token in key for token in ("completed", "done", "success", "ready")):
        return "success"
    if any(token in key for token in ("download", "running", "in progress", "exporting", "merging")):
        return "active"
    return "active"


def _tone_color(tone: str) -> str:
    return {
        "success": "#22C55E",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "active": "#38BDF8",
        "muted": "#60758C",
    }.get(tone, "#60758C")


def _split_step(text: str) -> tuple[str, str]:
    value = format_pipeline_step_text(text)
    if not value or value in {"—", "-"}:
        return "Not started", ""
    for separator in (" · ", " - ", " — "):
        if separator in value:
            head, tail = value.split(separator, 1)
            return head.strip() or "Not started", tail.strip()
    return value, ""


def _context_kind(stage: str, status: str, notes: str, error: str | None) -> str:
    stage_key = str(stage or "").strip().lower()
    status_key = str(status or "").strip().lower()
    note_key = str(notes or "").strip().lower()
    if error or stage_key == "error" or any(token in status_key for token in ("fail", "error")):
        return "failed"
    if "blocked" in status_key or "blocked" in note_key:
        return "blocked"
    if stage_key in {"done", "completed"} or status_key in {"done", "completed"}:
        return "completed"
    if any(token in f"{status_key} {note_key}" for token in ("wait", "pending", "download")):
        return "waiting"
    if notes:
        return "note"
    return ""


class ProgressDetailCard(StudioPanel):
    open_folder_requested = Signal(str)
    open_run_folder_requested = Signal(str)
    sync_manual_requested = Signal(str)
    view_history_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manual_mode = False
        self._inspections: dict[str, ManualAssetInspection] = {}
        self._syncing_batch_id = ""
        self._entry: EffectiveProgressRow | None = None
        self._batch_raw = ""
        self._export_issues: list[str] = []

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(380)
        self.setMaximumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(0)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(8)
        heading.addWidget(section_heading("ROW DETAIL", "search"), 1)
        self._status_badge = QLabel("")
        self._status_badge.setObjectName("ProgressDetailStatus")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.addWidget(self._status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(heading)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("ProgressDetailScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll.setAutoFillBackground(False)
        self._scroll.viewport().setAutoFillBackground(False)

        scroll_body = QWidget()
        scroll_body.setObjectName("ProgressDetailBody")
        scroll_body.setAutoFillBackground(False)
        body_layout = QVBoxLayout(scroll_body)
        body_layout.setContentsMargins(0, 10, 0, 4)
        body_layout.setSpacing(0)

        self._placeholder = QLabel(
            "No row selected\n\nSelect an operational row to inspect its pipeline status, files, and available actions."
        )
        self._placeholder.setObjectName("ProgressDetailEmpty")
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body_layout.addStretch(1)
        body_layout.addWidget(self._placeholder)
        body_layout.addStretch(1)

        self._content = QWidget()
        self._content.setObjectName("ProgressDetailContent")
        self._content.setAutoFillBackground(False)
        content = QVBoxLayout(self._content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)

        self._header = QLabel("")
        self._header.setObjectName("ProgressDetailTitle")
        self._header.setWordWrap(True)
        content.addWidget(self._header)

        self._state = QLabel("")
        self._state.setObjectName("ProgressDetailState")
        self._state.setWordWrap(True)
        self._state.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content.addWidget(self._state)

        self._meta = QLabel("")
        self._meta.setObjectName("ProgressDetailMeta")
        self._meta.setWordWrap(True)
        content.addWidget(self._meta)

        content.addWidget(self._rule())
        content.addWidget(self._section_label("PIPELINE STATUS"))

        self._converter_label = QLabel("")
        self._converter_detail = QLabel("")
        self._merge_label = QLabel("")
        self._merge_detail = QLabel("")
        self._youtube_label = QLabel("")
        self._youtube_detail = QLabel("")
        self._export_dot = self._status_dot()
        self._merge_dot = self._status_dot()
        self._youtube_dot = self._status_dot()
        content.addWidget(
            self._pipeline_list(
                ("video", "Export", self._export_dot, self._converter_label, self._converter_detail),
                ("layers", "Merge", self._merge_dot, self._merge_label, self._merge_detail),
                ("youtube", "YouTube", self._youtube_dot, self._youtube_label, self._youtube_detail),
            )
        )

        self._context_rule = self._rule()
        content.addWidget(self._context_rule)

        self._context = QFrame()
        self._context.setObjectName("ProgressDetailContext")
        self._context.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        context_layout = QVBoxLayout(self._context)
        context_layout.setContentsMargins(10, 8, 10, 8)
        context_layout.setSpacing(6)
        self._context_title = QLabel("")
        self._context_title.setObjectName("ProgressDetailContextTitle")
        self._notes = QLabel("")
        self._notes.setObjectName("ProgressDetailNoticeText")
        self._notes.setWordWrap(True)
        self._notes.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._error_label = QLabel("")
        self._error_label.setObjectName("progress_error_text")
        self._error_label.setWordWrap(True)
        self._error_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._completed_summary = QLabel("")
        self._completed_summary.setObjectName("ProgressDetailMeta")
        self._completed_summary.setWordWrap(True)
        context_layout.addWidget(self._context_title)
        context_layout.addWidget(self._notes)
        context_layout.addWidget(self._error_label)
        context_layout.addWidget(self._completed_summary)
        content.addWidget(self._context)

        self._manual_panel = NestedPanel()
        manual_layout = QVBoxLayout(self._manual_panel)
        manual_layout.setContentsMargins(10, 8, 10, 8)
        manual_layout.setSpacing(4)
        self._manual_status = QLabel("")
        self._manual_status.setObjectName("ProgressDetailMeta")
        self._manual_status.setWordWrap(True)
        self._manual_missing = QLabel("")
        self._manual_missing.setObjectName("progress_warning_text")
        self._manual_missing.setWordWrap(True)
        manual_layout.addWidget(self._manual_status)
        manual_layout.addWidget(self._manual_missing)
        content.addWidget(self._manual_panel)

        content.addWidget(self._rule())
        content.addWidget(self._section_label("BATCH"))
        self._batch_id = QLabel("")
        self._batch_id.setObjectName("ProgressDetailMeta")
        self._batch_id.setWordWrap(False)
        self._batch_id.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self._batch_id)

        content.addWidget(self._section_label("RUN FOLDER"))
        path_box = QFrame()
        path_box.setObjectName("ProgressDetailPath")
        path_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        path_row = QHBoxLayout(path_box)
        path_row.setContentsMargins(8, 6, 4, 6)
        path_row.setSpacing(4)
        self._run_dir = QLabel("")
        self._run_dir.setObjectName("ProgressDetailPathText")
        self._run_dir.setWordWrap(True)
        self._run_dir.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_row.addWidget(self._run_dir, 1)
        self._copy_path_btn = QPushButton()
        self._copy_path_btn.setObjectName("SecondaryButton")
        self._copy_path_btn.setFixedSize(24, 24)
        self._copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_path_btn.setToolTip("Copy run folder path")
        apply_button_icon(self._copy_path_btn, "copy", size=12)
        self._copy_path_btn.clicked.connect(self._copy_run_dir)
        path_row.addWidget(self._copy_path_btn, 0, Qt.AlignmentFlag.AlignTop)
        content.addWidget(path_box)

        self._open_run_btn = QPushButton("Open Run Folder")
        self._style_action_button(self._open_run_btn)
        apply_button_icon(self._open_run_btn, "folder-open")
        self._open_run_btn.clicked.connect(self._emit_open_run_folder)
        content.addWidget(self._open_run_btn)

        self._open_manual_btn = QPushButton("Open Manual Folder")
        self._style_action_button(self._open_manual_btn)
        apply_button_icon(self._open_manual_btn, "image")
        self._open_manual_btn.clicked.connect(self._emit_open_manual_folder)
        content.addWidget(self._open_manual_btn)

        self._continue_btn = QPushButton("Continue Pipeline")
        self._style_action_button(self._continue_btn)
        apply_button_icon(self._continue_btn, "refresh-cw")
        self._continue_btn.clicked.connect(self._emit_continue_pipeline)
        content.addWidget(self._continue_btn)
        content.addStretch(1)

        body_layout.insertWidget(0, self._content)
        self._content.hide()

        self._scroll.setWidget(scroll_body)
        root.addWidget(self._scroll, 1)

        self._notice = self._context

    @staticmethod
    def _rule() -> QFrame:
        line = QFrame()
        line.setObjectName("ProgressDetailRule")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("ProgressDetailSection")
        return label

    @staticmethod
    def _style_action_button(button: QPushButton) -> None:
        button.setObjectName("SecondaryButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(26)

    @staticmethod
    def _status_dot() -> QLabel:
        mark = QLabel()
        mark.setFixedSize(8, 8)
        mark.setStyleSheet("background-color: #60758C; border-radius: 4px; border: none;")
        return mark

    @staticmethod
    def _set_dot(dot: QLabel, tone: str) -> None:
        color = _tone_color(tone)
        if tone == "muted":
            dot.setStyleSheet(
                f"background: transparent; border: 1px solid {color}; border-radius: 4px;"
            )
        else:
            dot.setStyleSheet(f"background-color: {color}; border-radius: 4px; border: none;")

    @staticmethod
    def _pipeline_list(*steps: tuple[str, str, QLabel, QLabel, QLabel]) -> QWidget:
        host = QWidget()
        host.setObjectName("TransparentBlock")
        layout = QGridLayout(host)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)
        layout.setColumnStretch(3, 1)
        row_index = 0
        for icon_name, title, dot, headline, detail in steps:
            icon = icon_label(icon_name, size=12, color="#60758C")
            heading = QLabel(title.upper())
            heading.setObjectName("ProgressDetailStepLabel")
            heading.setFixedWidth(58)
            headline.setObjectName("ProgressDetailStepValue")
            headline.setWordWrap(True)
            detail.setObjectName("ProgressDetailStepHint")
            detail.setWordWrap(True)
            layout.addWidget(icon, row_index, 0, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(heading, row_index, 1, Qt.AlignmentFlag.AlignTop)
            layout.addWidget(dot, row_index, 2, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(headline, row_index, 3)
            layout.addWidget(detail, row_index + 1, 3)
            row_index += 2
        return host

    def set_manual_mode(self, enabled: bool) -> None:
        self._manual_mode = enabled
        self._render()

    def set_manual_inspections(self, inspections: dict[str, ManualAssetInspection]) -> None:
        self._inspections = inspections
        self._render()

    def set_syncing_batch_id(self, batch_id: str) -> None:
        self._syncing_batch_id = batch_id
        self._render()

    def set_entry(self, entry: EffectiveProgressRow | None) -> None:
        self._entry = entry
        if entry is None:
            self._export_issues = []
        self._render()

    def set_export_issues(self, issues: list[str]) -> None:
        self._export_issues = [str(issue).strip() for issue in issues if str(issue).strip()]
        self._render()

    def _export_status_text(self) -> str:
        if not self._export_issues:
            return ""
        lines = "\n".join(f"• {issue}" for issue in self._export_issues)
        return f"Export not ready:\n{lines}"

    def _render(self) -> None:
        entry = self._entry
        if entry is None:
            self._placeholder.show()
            self._content.hide()
            self._status_badge.hide()
            return

        self._placeholder.hide()
        self._content.show()
        self._status_badge.show()

        row = entry.row
        meta = row.meta
        self._header.setText(format_album_label(row.album) or "—")
        self._meta.setText(
            f"{format_run_date_label(row.run_date)} · "
            f"{row.channel} ({format_channel_role_label(meta.role)})"
        )
        self._state.setText(f"{entry.effective_stage} / {entry.effective_status}")
        self._apply_status_badge(entry.effective_status)
        batch_id = str(meta.batch_id or row.batch or "").strip()
        self._batch_raw = batch_id or "—"
        self._set_elided(self._batch_id, self._batch_raw)

        error_message = resolve_progress_error_message(
            row,
            effective_stage=entry.effective_stage,
            effective_status=entry.effective_status,
            effective_notes=entry.effective_notes,
        )
        notes = str(entry.effective_notes or row.notes or "").strip()
        kind = _context_kind(entry.effective_stage, entry.effective_status, notes, error_message)
        export_text = self._export_status_text()
        if export_text and kind not in {"failed", "blocked"}:
            extra = notes if notes and notes not in export_text else ""
            combined = export_text if not extra else f"{export_text}\n\n{extra}"
            self._apply_context("note", notes=combined, error=None, row=row)
        else:
            self._apply_context(kind, notes=notes, error=error_message, row=row)

        export_raw = format_pipeline_step_text(entry.effective_converter or row.converter)
        merge_raw = format_pipeline_step_text(entry.effective_merge or row.merge)
        youtube_raw = format_youtube_compact(row)
        if meta.youtube_url:
            youtube_raw = f"{youtube_raw} · {meta.youtube_url}" if youtube_raw not in {"—", ""} else meta.youtube_url
        self._bind_step(self._converter_label, self._converter_detail, self._export_dot, export_raw)
        self._bind_step(self._merge_label, self._merge_detail, self._merge_dot, merge_raw)
        self._bind_step(self._youtube_label, self._youtube_detail, self._youtube_dot, youtube_raw)

        run_dir = str(meta.run_dir or "").strip()
        self._run_dir.setText(run_dir or "—")
        self._run_dir.setToolTip(run_dir)
        self._copy_path_btn.setEnabled(bool(run_dir))
        self._open_run_btn.setVisible(bool(run_dir))

        if self._manual_mode:
            key = manual_inspection_key(meta.batch_id, meta.profile_id, meta.role)
            inspection = self._inspections.get(key)
            self._manual_panel.show()
            self._open_manual_btn.setVisible(bool(inspection and inspection.directory))
            if inspection is None:
                self._manual_status.setText("Loading manual-folder status...")
                self._manual_missing.hide()
                self._continue_btn.hide()
            else:
                self._manual_status.setText(
                    f"Manual assets: {inspection.ready_count}/{inspection.total} ready · "
                    f"Long: {'Ready' if meta.long_ready else 'Missing'} · "
                    f"Reel: {'Ready' if meta.reel_ready else 'Missing'}\n"
                    f"{inspection.directory}"
                )
                if inspection.ready:
                    self._manual_missing.hide()
                else:
                    self._manual_missing.setText(
                        f"Missing: {', '.join(inspection.missing_labels)}"
                    )
                    self._manual_missing.show()
                show_continue = (
                    inspection.ready
                    and entry.effective_stage.lower() == "image"
                )
                self._continue_btn.setVisible(show_continue)
                self._continue_btn.setText(
                    "Syncing..." if self._syncing_batch_id == meta.batch_id else "Continue Pipeline"
                )
                self._continue_btn.setEnabled(self._syncing_batch_id != meta.batch_id)
        else:
            self._manual_panel.hide()
            self._open_manual_btn.hide()
            self._continue_btn.hide()

    def _apply_context(
        self,
        kind: str,
        *,
        notes: str,
        error: str | None,
        row,
    ) -> None:
        titles = {
            "waiting": "WAITING",
            "failed": "FAILED",
            "blocked": "BLOCKED",
            "completed": "COMPLETED",
            "note": "STATUS",
        }
        if not kind:
            self._context.hide()
            self._context_rule.hide()
            return

        self._context.show()
        self._context_rule.show()
        self._context.setProperty("kind", kind)
        self._context.style().unpolish(self._context)
        self._context.style().polish(self._context)
        self._context_title.setText(titles[kind])

        if kind == "completed":
            self._notes.hide()
            self._error_label.hide()
            meta = row.meta
            lines = [
                "Music generation completed." if meta.saved >= max(1, meta.expected) else "Pipeline completed.",
                f"{meta.saved} / {max(1, meta.expected)} songs",
                f"Background {meta.bg_ready} / {max(1, meta.bg_total)}",
                f"Thumbnail {meta.th_ready} / {max(1, meta.th_total)}",
            ]
            self._completed_summary.setText("\n".join(lines))
            self._completed_summary.show()
            return

        self._completed_summary.hide()
        if kind == "failed":
            self._notes.setText(notes if notes and notes != error else "Error")
            self._notes.setVisible(bool(self._notes.text()))
            if error:
                self._error_label.setText(error)
                self._error_label.show()
            else:
                self._error_label.hide()
            return

        self._error_label.hide()
        body = notes or error or ""
        self._notes.setText(body)
        self._notes.setVisible(bool(body))

    def _bind_step(self, headline: QLabel, detail: QLabel, dot: QLabel, raw: str) -> None:
        head, tail = _split_step(raw)
        headline.setText(head)
        detail.setText(tail)
        detail.setVisible(bool(tail))
        self._set_dot(dot, _status_tone(raw if raw not in {"—", "-"} else head))

    @staticmethod
    def _set_elided(label: QLabel, text: str) -> None:
        value = str(text or "").strip() or "—"
        label.setToolTip(value if value != "—" else "")
        width = label.width()
        if width <= 8:
            label.setText(value)
            return
        label.setText(
            label.fontMetrics().elidedText(value, Qt.TextElideMode.ElideMiddle, max(width - 2, 24))
        )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._entry is None:
            return
        self._set_elided(self._batch_id, self._batch_raw)

    def _apply_status_badge(self, status: str) -> None:
        text = str(status or "").strip() or "—"
        self._status_badge.setText(text)
        tone = _status_tone(text)
        self._status_badge.setProperty("tone", tone)
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

    def _copy_text(self, value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)

    def _copy_run_dir(self) -> None:
        if self._entry and self._entry.row.meta.run_dir:
            self._copy_text(self._entry.row.meta.run_dir)
            self._copy_path_btn.setToolTip("Path copied")
            QTimer.singleShot(1500, lambda: self._copy_path_btn.setToolTip("Copy run folder path"))

    def _copy_batch_id(self) -> None:
        if self._entry is None:
            return
        self._copy_text(self._entry.row.meta.batch_id or self._entry.row.batch)

    def _emit_view_history(self) -> None:
        if self._entry is None:
            return
        batch_id = str(self._entry.row.meta.batch_id or self._entry.row.batch or "").strip()
        if batch_id:
            self._copy_text(batch_id)
            self.view_history_requested.emit(batch_id)

    def _emit_open_run_folder(self) -> None:
        if self._entry and self._entry.row.meta.run_dir:
            self.open_run_folder_requested.emit(self._entry.row.meta.run_dir)

    def _emit_open_manual_folder(self) -> None:
        if self._entry is None:
            return
        key = manual_inspection_key(
            self._entry.row.meta.batch_id,
            self._entry.row.meta.profile_id,
            self._entry.row.meta.role,
        )
        inspection = self._inspections.get(key)
        if inspection and inspection.directory:
            self.open_folder_requested.emit(inspection.directory)

    def _emit_continue_pipeline(self) -> None:
        if self._entry:
            self.sync_manual_requested.emit(self._entry.row.meta.batch_id)
