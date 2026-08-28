"""Files table and search, matching the standalone Create screen."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from PySide6.QtCore import QSize, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.audio_player import AudioPlayer
from features.create.widgets.icons import create_icon
from shared.lib.create_history import (
    download_root_from_file,
    history_slots,
    is_encrypted_audio_file,
    match_local_files,
    matches_search,
)
from shared.lib.ui_font import content_font
from shared.models.web_music import WebMusicGenerationResponse
from shared.services.shell_status import emit_shell_status

_FORMAT_KINDS = ("mp3", "wav", "lrc", "srt")
_FILE_HEADERS = ["File", "Version", "MP3", "WAV", "LRC", "SRT", "State"]
COL_FILE = 0
COL_VERSION = 1
COL_STATE = 6
_FORMAT_COLUMNS = {2: "mp3", 3: "wav", 4: "lrc", 5: "srt"}
_MUTED = QColor("#5a7a8a")
VERSION_1 = "Version 1"
VERSION_2 = "Version 2"
STATE_GENERATING = "Generating…"
STATE_READY = "Ready"
STATE_FAILED = "Failed"
MISSING_MESSAGE = "Not downloaded — right-click to download"
_DOWNLOAD_KINDS = (
    ("mp3", "Download MP3"),
    ("wav", "Download WAV"),
    ("lrc", "Download LRC"),
    ("srt", "Download SRT"),
)
_BADGE_COLORS = {
    STATE_READY: "#00C878",
    STATE_GENERATING: "#F59E0B",
    STATE_FAILED: "#F43F5E",
}


@dataclass
class _PendingSlot:
    index: int
    title: str
    state: str = STATE_GENERATING
    path_v1: str = ""
    path_v2: str = ""
    task_id: str = ""
    created: str = ""


@dataclass
class _VersionFiles:
    mp3: str = ""
    wav: str = ""
    lrc: str = ""
    srt: str = ""

    def get(self, kind: str) -> str:
        return str(getattr(self, kind, "") or "")

    def preferred_audio(self) -> str:
        for kind in ("mp3", "wav"):
            path = self.get(kind)
            if path and Path(path).is_file():
                return path
        return ""

    def any_file(self) -> str:
        for kind in _FORMAT_KINDS:
            path = self.get(kind)
            if path and Path(path).is_file():
                return path
        return ""

    def paths(self) -> list[str]:
        return [self.get(kind) for kind in _FORMAT_KINDS if self.get(kind)]


@dataclass
class _InventoryRow:
    label: str
    version: str
    which: str
    state: str
    files: _VersionFiles = field(default_factory=_VersionFiles)
    slot: _PendingSlot | None = None

    def preferred_audio(self) -> str:
        return self.files.preferred_audio()

    def any_file(self) -> str:
        return self.files.any_file()

    def path_for(self, kind: str) -> str:
        return self.files.get(kind)

    def contains_path(self, path: str) -> bool:
        return path in self.files.paths()

    def cells(self) -> list[str]:
        return [
            self.label,
            self.version,
            _audio_cell(self.files.mp3),
            _audio_cell(self.files.wav),
            _text_cell(self.files.lrc),
            _text_cell(self.files.srt),
            self.state,
        ]


class FilePanel(QFrame):
    track_selected = Signal(str)
    play_requested = Signal(str)
    download_requested = Signal(str, str, str, str, str)
    retry_download_requested = Signal(int, str, str)
    retry_song_requested = Signal(int)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._folder = ""
        self._rows: list[_InventoryRow] = []
        self._pending: list[_PendingSlot] = []
        self._history: list[_PendingSlot] = []
        self._query = ""
        self._playing_path = ""
        self._playlist: list[str] = []
        self._playlist_index = -1
        self._download_root = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("FILES")
        title.setObjectName("SectionLabel")
        refresh = QToolButton()
        refresh.setObjectName("FilesRefresh")
        refresh.setAutoRaise(True)
        refresh.setIcon(create_icon("refresh-cw", size=14, color="#8FA4BB"))
        refresh.setIconSize(QSize(14, 14))
        refresh.setToolTip("Refresh")
        refresh.setStyleSheet("QToolButton { background: transparent; border: none; padding: 2px; }")
        refresh.clicked.connect(self.refresh_requested.emit)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(refresh)
        root.addLayout(header)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search older songs...")
        self.search.addAction(create_icon("search", size=14, color="#60758C"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._on_search)
        root.addWidget(self.search)

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("FileTable")
        self.table.setHorizontalHeaderLabels(list(_FILE_HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 6):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 96)
        self.table.setFont(content_font(15))
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.itemSelectionChanged.connect(self._emit_selection)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.table, 1)

        self.player = AudioPlayer()
        root.addWidget(self.player)

        self._table = self.table
        self._now_playing = self.player.track
        self._play_btn = self.player.play
        self._stop_btn = self.player.stop
        self._next_btn = self.player.next
        self._back_btn = self.player.back

    def set_folder(self, folder: str) -> None:
        self._folder = folder.strip()
        self.refresh()

    def set_history(self, items: list[WebMusicGenerationResponse]) -> None:
        self._history = [
            _PendingSlot(
                index=int(row["index"]),
                title=str(row["title"]),
                state=str(row["state"]),
                task_id=str(row["task_id"]),
                created=str(row["created"]),
            )
            for row in history_slots(items)
        ]
        history_ids = {slot.task_id for slot in self._history if slot.task_id}
        self._pending = [
            slot
            for slot in self._pending
            if slot.state == STATE_GENERATING
            or not slot.task_id
            or slot.task_id not in history_ids
        ]
        self.refresh()

    def begin_generate(self, count: int, title: str = "") -> None:
        hint = (title or "").strip() or "Song"
        total = max(1, int(count))
        self._pending = [
            _PendingSlot(index=index, title=_slot_title(hint, index, total))
            for index in range(1, total + 1)
        ]
        self.refresh()

    def update_pending_title(self, index: int, title: str) -> None:
        slot = self._slot(index)
        if slot is None:
            return
        cleaned = (title or "").strip()
        if cleaned:
            slot.title = cleaned
        self.refresh()

    def attach_task(self, index: int, task_id: str, title: str = "") -> None:
        slot = self._slot(index) or self._slot_by_task(task_id)
        if slot is None:
            return
        slot.task_id = (task_id or "").strip()
        if title.strip():
            slot.title = title.strip()
        slot.state = STATE_GENERATING
        self.refresh()

    def mark_ready(self, index: int, path_v1: str, path_v2: str) -> None:
        slot = self._slot(index)
        if slot is None:
            return
        slot.state = STATE_READY
        if path_v1:
            slot.path_v1 = path_v1
        if path_v2:
            slot.path_v2 = path_v2
        self.refresh()

    def mark_file(self, task_id: str, which: str, path: str) -> None:
        slot = self._slot_by_task(task_id)
        if slot is None or not path:
            self.refresh()
            return
        slot.state = STATE_READY
        if which == "v2":
            slot.path_v2 = path
        else:
            slot.path_v1 = path
        self.refresh()

    def mark_failed(self, index: int | None = None) -> None:
        if index is None:
            for slot in self._pending:
                if slot.state == STATE_GENERATING:
                    slot.state = STATE_FAILED
        else:
            slot = self._slot(index)
            if slot is not None and slot.state != STATE_READY:
                slot.state = STATE_FAILED
        self.refresh()

    def refresh(self) -> None:
        root = Path(self._folder) if self._folder else None
        folder_v1 = root / VERSION_1 if root else None
        folder_v2 = root / VERSION_2 if root else None
        rows, claimed = self._build_slot_rows(folder_v1, folder_v2)
        rows.extend(self._build_orphan_rows(folder_v1, folder_v2, claimed))
        self._rows = rows
        self._fill_rows(rows)

    def current_title(self) -> str:
        row = self.table.currentRow()
        inventory = self._row_at(row)
        if inventory is None:
            return "No track selected"
        return f"{inventory.label} · {inventory.version}"

    def play_current(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            for index in range(self.table.rowCount()):
                if not self.table.isRowHidden(index):
                    row = index
                    break
        inventory = self._row_at(row)
        if inventory is None:
            return
        self._activate_preferred(inventory)

    def play_path(self, path: str) -> None:
        target = Path(path)
        if not target.is_file():
            return
        if is_encrypted_audio_file(target):
            self.player.set_track("Encrypted file — right-click Download MP3")
            return
        self._set_playlist_from_path(str(target))
        self._playing_path = str(target)
        self.player.set_track(target.stem)
        self.play_requested.emit(self._playing_path)

    def select_relative(self, delta: int) -> None:
        visible = [row for row in range(self.table.rowCount()) if not self.table.isRowHidden(row)]
        if not visible:
            return
        current = self.table.currentRow()
        if current not in visible:
            target = visible[0] if delta >= 0 else visible[-1]
        else:
            index = visible.index(current) + delta
            if index < 0 or index >= len(visible):
                return
            target = visible[index]
        self.table.selectRow(target)
        inventory = self._row_at(target)
        if inventory is not None:
            self._activate_preferred(inventory)

    def row_state(self, row: int) -> str:
        item = self.table.item(row, COL_STATE)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "")

    def _fill_rows(self, rows: list[_InventoryRow]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = row.cells()
            for col, value in enumerate(values[:-1]):
                item = QTableWidgetItem(value)
                item.setFont(content_font(15))
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col in _FORMAT_COLUMNS and value == "No":
                    item.setForeground(_MUTED)
                self.table.setItem(row_index, col, item)
            state_item = QTableWidgetItem("")
            state_item.setData(Qt.ItemDataRole.UserRole, row.state)
            state_item.setFlags(state_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, COL_STATE, state_item)
            self.table.setCellWidget(row_index, COL_STATE, _state_badge(row.state))

    def _on_search(self, text: str) -> None:
        self._query = text
        self.refresh()

    def _filter(self, query: str) -> None:
        self._on_search(query)

    def _emit_selection(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        self.player.set_track(self.current_title())
        self.track_selected.emit(self.current_title())

    def _display_slots(self) -> list[_PendingSlot]:
        used = {slot.task_id for slot in self._pending if slot.task_id}
        slots = list(self._pending)
        for slot in self._history:
            if slot.task_id and slot.task_id in used:
                continue
            slots.append(slot)
        if not self._query.strip():
            return slots
        return [slot for slot in slots if matches_search(slot.title, self._query)]

    def _slot(self, index: int) -> _PendingSlot | None:
        for slot in (*self._pending, *self._history):
            if slot.index == index:
                return slot
        return None

    def _slot_by_task(self, task_id: str) -> _PendingSlot | None:
        token = (task_id or "").strip()
        if not token:
            return None
        for slot in (*self._pending, *self._history):
            if slot.task_id == token:
                return slot
        return None

    def _build_slot_rows(
        self,
        folder_v1: Path | None,
        folder_v2: Path | None,
    ) -> tuple[list[_InventoryRow], set[str]]:
        claimed: set[str] = set()
        rows: list[_InventoryRow] = []
        for slot in self._display_slots():
            v1 = _resolve_version_files(folder_v1, slot.path_v1, slot.title, slot.task_id)
            v2 = _resolve_version_files(folder_v2, slot.path_v2, slot.title, slot.task_id)
            if v1.preferred_audio():
                slot.path_v1 = v1.preferred_audio()
            if v2.preferred_audio():
                slot.path_v2 = v2.preferred_audio()
            rows.append(
                _InventoryRow(
                    label=slot.title,
                    version=VERSION_1,
                    which="v1",
                    state=slot.state,
                    files=v1,
                    slot=slot,
                )
            )
            rows.append(
                _InventoryRow(
                    label=slot.title,
                    version=VERSION_2,
                    which="v2",
                    state=slot.state,
                    files=v2,
                    slot=slot,
                )
            )
            for path in (*v1.paths(), *v2.paths()):
                target = Path(path)
                claimed.add(str(target.resolve()) if target.exists() else path)
        return rows, claimed

    def _build_orphan_rows(
        self,
        folder_v1: Path | None,
        folder_v2: Path | None,
        claimed: set[str],
    ) -> list[_InventoryRow]:
        by_key: dict[tuple[str, str], _InventoryRow] = {}
        for folder, which, version in (
            (folder_v1, "v1", VERSION_1),
            (folder_v2, "v2", VERSION_2),
        ):
            if folder is None or not folder.is_dir():
                continue
            for path in _iter_format_files(folder):
                resolved = str(path.resolve()) if path.exists() else str(path)
                if resolved in claimed or str(path) in claimed:
                    continue
                if self._query.strip() and not matches_search(path.stem, self._query):
                    continue
                key = (path.stem.lower(), which)
                row = by_key.get(key)
                if row is None:
                    row = _InventoryRow(
                        label=path.stem,
                        version=version,
                        which=which,
                        state=STATE_READY,
                    )
                    by_key[key] = row
                setattr(row.files, path.suffix.lower().lstrip("."), str(path))
        return list(by_key.values())

    def _on_context_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        inventory = self._row_at(row)
        slot = inventory.slot if inventory is not None else None
        menu = QMenu(self)
        if slot is not None and slot.task_id:
            which = inventory.which if inventory is not None else "v1"
            for kind, kind_label in _DOWNLOAD_KINDS:
                action = menu.addAction(kind_label)
                action.triggered.connect(partial(self._emit_download, slot, kind, which))
        if slot is not None and slot.state != STATE_READY and not slot.task_id:
            action = menu.addAction("Retry this song")
            action.triggered.connect(partial(self.retry_song_requested.emit, slot.index))
        path = inventory.any_file() if inventory is not None else ""
        if path and Path(path).is_file():
            action = menu.addAction("Open folder")
            action.triggered.connect(partial(self._open_folder, download_root_from_file(path)))
        if menu.actions():
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _emit_download(self, slot: _PendingSlot, kind: str, which: str) -> None:
        folder = self._resolve_download_root(which, slot)
        if not folder:
            return
        variant = "alt" if which == "v2" else "ok"
        self.download_requested.emit(slot.task_id, slot.title, kind, variant, folder)

    def _resolve_download_root(self, which: str, slot: _PendingSlot) -> str:
        first = slot.path_v1 if which == "v1" else slot.path_v2
        second = slot.path_v2 if which == "v1" else slot.path_v1
        for path in (first, second):
            if path and Path(path).is_file():
                return download_root_from_file(path)
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Download files to",
            self._download_root,
        ).strip()
        if chosen:
            self._download_root = chosen
        return chosen

    def _open_folder(self, folder: str) -> None:
        target = Path(folder)
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _open_local_file(self, path: str) -> None:
        target = Path(path)
        if not target.is_file():
            self._show_missing()
            return
        self.player.set_track(target.name)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _row_at(self, row: int) -> _InventoryRow | None:
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        inventory = self._row_at(row)
        if inventory is None:
            return
        if column == COL_FILE:
            self._activate_preferred(inventory)
            return
        if column in {COL_VERSION, COL_STATE}:
            return
        kind = _FORMAT_COLUMNS.get(column)
        if kind is None:
            return
        path = inventory.path_for(kind)
        if not path or not Path(path).is_file():
            self._show_missing(inventory.state == STATE_GENERATING)
            return
        if kind in {"mp3", "wav"}:
            self.play_path(path)
            return
        self._open_local_file(path)

    def _activate_preferred(self, inventory: _InventoryRow) -> None:
        path = inventory.preferred_audio()
        if path:
            self.play_path(path)
            return
        self._show_missing(inventory.state == STATE_GENERATING)

    def _show_missing(self, generating: bool = False) -> None:
        message = "Still generating…" if generating else MISSING_MESSAGE
        self.player.set_track(message)
        emit_shell_status(message)

    def _set_playlist_from_path(self, path: str) -> None:
        playlist: list[str] = []
        current = -1
        for row in self._rows:
            if row.contains_path(path):
                current = len(playlist)
                playlist.append(path)
                continue
            audio = row.preferred_audio()
            if audio:
                playlist.append(audio)
        if current < 0:
            playlist = [path]
            current = 0
        self._playlist = playlist
        self._playlist_index = current


def _resolve_version_files(
    folder: Path | None,
    stored: str,
    title: str,
    task_id: str,
) -> _VersionFiles:
    found = match_local_files(folder, title=title, task_id=task_id)
    hint = Path(stored) if stored else None
    if hint is not None and hint.is_file():
        kind = hint.suffix.lower().lstrip(".")
        if kind in _FORMAT_KINDS and not found.get(kind):
            found[kind] = str(hint)
        for extra in _FORMAT_KINDS:
            if found.get(extra):
                continue
            sibling = hint.with_suffix(f".{extra}")
            if sibling.is_file():
                found[extra] = str(sibling)
    return _VersionFiles(
        mp3=found.get("mp3", ""),
        wav=found.get("wav", ""),
        lrc=found.get("lrc", ""),
        srt=found.get("srt", ""),
    )


def _audio_cell(path: str) -> str:
    target = Path(path) if path else None
    if target is not None and target.is_file():
        return _format_size(target.stat().st_size)
    return "No"


def _text_cell(path: str) -> str:
    return "Yes" if path and Path(path).is_file() else "No"


def _slot_title(hint: str, index: int, total: int) -> str:
    if total <= 1:
        return hint
    return f"{hint} ({index})"


def _iter_format_files(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower().lstrip(".") in _FORMAT_KINDS
        ),
        key=lambda item: item.name.lower(),
    )


def _format_size(nbytes: int) -> str:
    if nbytes < 1024:
        return f"{nbytes} B"
    kb = nbytes / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    return f"{kb / 1024.0:.1f} MB"


def _state_badge(state: str) -> QWidget:
    badge = QLabel(state)
    badge.setObjectName("StatusBadge")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedHeight(16)
    badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    color = _BADGE_COLORS.get(state, "#8FA4BB")
    badge.setStyleSheet(
        "QLabel#StatusBadge {"
        f" background-color: {color}; color: #ffffff; border: none;"
        " border-radius: 3px; padding: 0 7px;"
        " font-size: 10px; font-weight: 600;"
        "}"
    )
    wrap = QWidget()
    wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    wrap.setAutoFillBackground(False)
    wrap.setStyleSheet("background: transparent; border: none;")
    wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    cell = QHBoxLayout(wrap)
    cell.setContentsMargins(0, 0, 0, 0)
    cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cell.addWidget(badge)
    return wrap
