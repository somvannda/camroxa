"""Per-track header row — Lucide type badge, name, M/S/L/H icons, drag-to-reorder."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from studio.core.models import Track
from studio.ui.icons.lucide_icons import (
    ICON_COLOR_ACTIVE,
    ICON_COLOR_DIM,
    ICON_SZ_HEADER,
    lucide_pixmap,
    set_button_lucide_icon,
    track_badge_pixmap,
)
from studio.ui.timeline.geometry import TRACK_BADGE_SIZE, TRACK_HEADER_WIDTH, TRACK_HEIGHT

_DANGER = "#ff5470"
_TYPE_NAME_PREFIX = {"video": "Video ", "audio": "Audio ", "overlay": "Overlay "}


def display_track_name(track: Track) -> str:
    """Short header label — type is shown by the badge icon, not repeated in text."""
    name = track.name.strip()
    prefix = _TYPE_NAME_PREFIX.get(track.type, "")
    if prefix and name.startswith(prefix):
        short = name[len(prefix) :].strip()
        if short:
            return short
    return name or "1"


def _header_icon_btn(icon_name: str, tooltip: str) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(20, 20)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(
        "QPushButton { border: 1px solid #33333f; border-radius: 4px; background: #1b1b25; padding: 0; }"
        "QPushButton:hover { border-color: #5c5c6e; background: #252530; }"
        "QPushButton:disabled { opacity: 0.35; }"
    )
    set_button_lucide_icon(btn, icon_name, size=ICON_SZ_HEADER, color=ICON_COLOR_DIM)
    return btn


class EmptySlotHeaderRow(QFrame):
    """One generic drop row — no pre-assigned track type."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(TRACK_HEIGHT)
        self.setStyleSheet("QFrame { border-bottom: 1px solid #20202b; background: #101016; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        badge = QLabel()
        badge.setFixedSize(TRACK_BADGE_SIZE, TRACK_BADGE_SIZE)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setPixmap(lucide_pixmap("layers", size=12, color=ICON_COLOR_DIM))
        badge.setStyleSheet("background: #3a3a48; border-radius: 5px;")
        layout.addWidget(badge)

        label = QLabel("Drop media here")
        label.setStyleSheet("color: #5c5c6e; font-size: 11px; font-weight: 500;")
        layout.addWidget(label, 1)


class TrackHeaderRow(QFrame):
    mute_requested = Signal(str)
    solo_requested = Signal(str)
    lock_requested = Signal(str)
    hide_requested = Signal(str)
    delete_requested = Signal(str)
    rename_requested = Signal(str, str)
    reorder_requested = Signal(str, int)  # track_id, new_index

    _DRAG_THRESHOLD_PX = 6

    def __init__(self, track: Track, row_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.track_id = track.id
        self._scene_managed = bool(track.scene_role)
        self._row_index = row_index
        self._drag_start_y: float | None = None
        self._dragging = False
        self.setFixedHeight(TRACK_HEIGHT)
        self.setStyleSheet("QFrame { border-bottom: 1px solid #20202b; background: #14141b; }")
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        self.grip_label = QLabel()
        self.grip_label.setFixedWidth(10)
        self.grip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grip_label.setPixmap(lucide_pixmap("grip-vertical", size=10, color="#4a4a5a"))
        self.grip_label.setToolTip("Drag to reorder track")
        layout.addWidget(self.grip_label)

        self.type_badge = QLabel()
        self.type_badge.setFixedSize(TRACK_BADGE_SIZE, TRACK_BADGE_SIZE)
        self.type_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.type_badge)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        self.name_label = QLabel(display_track_name(track))
        self.name_label.setStyleSheet("color: #d8d8e8; font-size: 12px; font-weight: 500;")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.name_label.installEventFilter(self)
        self.name_edit = QLineEdit(track.name)
        self.name_edit.setVisible(False)
        self.name_edit.returnPressed.connect(self._commit_rename)
        self.name_edit.editingFinished.connect(self._commit_rename)
        text_col.addWidget(self.name_label)
        text_col.addWidget(self.name_edit)
        layout.addLayout(text_col, 1)

        btn_col = QHBoxLayout()
        btn_col.setSpacing(2)
        self.mute_btn = _header_icon_btn("volume-2", "Mute")
        self.solo_btn = _header_icon_btn("headphones", "Solo")
        self.lock_btn = _header_icon_btn("lock-open", "Lock track")
        self.hide_btn = _header_icon_btn("eye", "Hide")
        self.delete_btn = _header_icon_btn("trash-2", "Delete track")
        self.mute_btn.clicked.connect(lambda: self.mute_requested.emit(self.track_id))
        self.solo_btn.clicked.connect(lambda: self.solo_requested.emit(self.track_id))
        self.lock_btn.clicked.connect(lambda: self.lock_requested.emit(self.track_id))
        self.hide_btn.clicked.connect(lambda: self.hide_requested.emit(self.track_id))
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.track_id))
        for btn in (self.mute_btn, self.solo_btn, self.lock_btn, self.hide_btn, self.delete_btn):
            btn_col.addWidget(btn)
        layout.addLayout(btn_col)

        self.set_track(track)

    def set_row_index(self, row_index: int) -> None:
        self._row_index = row_index

    def _is_drag_zone(self, pos) -> bool:
        return pos.x() < self.width() - 108

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._scene_managed:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton and self._is_drag_zone(event.position()):
            self._drag_start_y = event.globalPosition().y()
            self._dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start_y is not None and event.buttons() & Qt.MouseButton.LeftButton:
            dy = abs(event.globalPosition().y() - self._drag_start_y)
            if dy >= self._DRAG_THRESHOLD_PX:
                self._dragging = True
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_start_y is not None and event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                dy = event.globalPosition().y() - self._drag_start_y
                row_delta = int(round(dy / TRACK_HEIGHT))
                if row_delta != 0:
                    self.reorder_requested.emit(self.track_id, self._row_index + row_delta)
            self._drag_start_y = None
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.name_label and event.type() == QEvent.Type.MouseButtonDblClick:
            self._start_rename(event)
            return True
        return super().eventFilter(obj, event)

    def _start_rename(self, _event) -> None:
        self.name_label.setVisible(False)
        self.name_edit.setText(self.name_label.text())
        self.name_edit.setVisible(True)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _commit_rename(self) -> None:
        if not self.name_edit.isVisible():
            return
        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)
        self.rename_requested.emit(self.track_id, self.name_edit.text())

    def set_track(self, track: Track) -> None:
        self._scene_managed = bool(track.scene_role)
        if self._scene_managed:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.grip_label.setToolTip("Auto-managed playlist scene track")
        else:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.grip_label.setToolTip("Drag to reorder track")
        self.type_badge.setPixmap(track_badge_pixmap(track.type, scene_role=track.scene_role))
        shown = display_track_name(track)
        self.name_label.setText(shown)
        if not self.name_edit.isVisible():
            self.name_edit.setText(track.name)

        active = ICON_COLOR_ACTIVE
        off = ICON_COLOR_DIM
        danger = _DANGER

        set_button_lucide_icon(
            self.mute_btn,
            "volume-x" if track.muted else "volume-2",
            size=ICON_SZ_HEADER,
            color=active if track.muted else off,
        )
        set_button_lucide_icon(self.solo_btn, "headphones", size=ICON_SZ_HEADER, color=active if track.solo else off)
        set_button_lucide_icon(
            self.lock_btn,
            "lock" if track.locked else "lock-open",
            size=ICON_SZ_HEADER,
            color=active if track.locked else off,
        )
        is_hidden = track.hidden if track.type != "audio" else False
        set_button_lucide_icon(
            self.hide_btn,
            "eye-off" if is_hidden else "eye",
            size=ICON_SZ_HEADER,
            color=danger if is_hidden else off,
        )
        set_button_lucide_icon(self.delete_btn, "trash-2", size=ICON_SZ_HEADER, color=off)
        if track.locked or track.scene_role:
            self.delete_btn.setEnabled(False)
            tip = "Managed playlist scene track" if track.scene_role else "Unlock track to delete"
            self.delete_btn.setToolTip(tip)
        else:
            self.delete_btn.setEnabled(True)
            self.delete_btn.setToolTip("Delete track")
        if track.type == "audio":
            self.hide_btn.setEnabled(False)
            self.hide_btn.setToolTip("Hide (video/overlay only)")
        else:
            self.hide_btn.setEnabled(True)
            self.hide_btn.setToolTip("Hide")


class TrackHeaders(QWidget):
    mute_requested = Signal(str)
    solo_requested = Signal(str)
    lock_requested = Signal(str)
    hide_requested = Signal(str)
    delete_requested = Signal(str)
    rename_requested = Signal(str, str)
    reorder_requested = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(TRACK_HEADER_WIDTH)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._rows: dict[str, TrackHeaderRow] = {}

    def rebuild(self, tracks: list[Track], *, visible_rows: int | None = None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._rows.clear()

        row_count = visible_rows if visible_rows is not None else max(len(tracks), 1)
        self.setFixedHeight(row_count * TRACK_HEIGHT)
        for i in range(row_count):
            track = tracks[i] if i < len(tracks) else None
            if track is not None:
                row = TrackHeaderRow(track, i, self)
                row.mute_requested.connect(self.mute_requested.emit)
                row.solo_requested.connect(self.solo_requested.emit)
                row.lock_requested.connect(self.lock_requested.emit)
                row.hide_requested.connect(self.hide_requested.emit)
                row.delete_requested.connect(self.delete_requested.emit)
                row.rename_requested.connect(self.rename_requested.emit)
                row.reorder_requested.connect(self.reorder_requested.emit)
                self._rows[track.id] = row
            else:
                row = EmptySlotHeaderRow(self)
            self._layout.addWidget(row)

    def refresh_states(self, tracks: list[Track]) -> None:
        for i, track in enumerate(tracks):
            row = self._rows.get(track.id)
            if row is not None:
                row.set_row_index(i)
                row.set_track(track)
