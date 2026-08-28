"""Channel profiles table, toolbar, and row actions."""

from __future__ import annotations

from uuid import uuid4

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from features.create.create_styles import (
    STUDIO_BORDER_STRONG,
    STUDIO_PANEL,
    STUDIO_PURPLE,
    STUDIO_SUCCESS,
    STUDIO_TEXT,
    STUDIO_TEXT_DIM,
    STUDIO_TEXT_MUTED,
    STUDIO_WARNING,
)
from features.create.widgets.studio_controls import StudioComboBox
from features.create.widgets.studio_panel import StudioPanel
from features.profile.dialogs.profile_dialog import ProfileDialog
from features.profile.profile_constants import PAGE_SIZE
from features.profile.profile_format import title_visibility, visibility_key
from features.profile.widgets.icons import (
    color_for_name,
    initials_from_name,
    paint_initials_avatar,
    profile_icon,
    visibility_dot,
)
from shared.icons.lucide_icons import lucide_pixmap
from features.profile.widgets.profile_table_model import (
    COL_ACTIONS,
    COL_NAME,
    COL_VISIBILITY,
    ProfileTableModel,
)
from shared.lib.settings_workspace import get_profile_search_haystack
from shared.lib.ui_font import studio_font
from shared.models.auth import ProfileResponse
from shared.models.platform import DashboardOverview, profile_visibility
from shared.services.action_feedback import notify_action
from shared.services.local_user_scope import get_user_workspace_dir
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import DeleteProfileWorker, SaveProfileWorker

PROFILES_SUBTITLE = "Profiles available for generation and publication workflows."
LOADING_PROFILES = "Loading profiles..."
EMPTY_PROFILES = "No channel profiles found yet."

_VISIBILITY_COLORS = {
    "public": STUDIO_SUCCESS,
    "unlisted": STUDIO_WARNING,
    "private": STUDIO_TEXT_DIM,
    "scheduled": STUDIO_PURPLE,
}


class _TableItem:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class ProfileTable(QTableView):
    def __init__(self, model: ProfileTableModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ProfileTable")
        self.setModel(model)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(33)
        self.setIconSize(QSize(16, 16))
        self.setFont(studio_font(12))
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(STUDIO_PURPLE))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(STUDIO_TEXT))
        self.setPalette(palette)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_VISIBILITY, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_VISIBILITY, 110)
        header.setSectionResizeMode(COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_ACTIONS, 40)
        self._gear = QToolButton(header)
        self._gear.setObjectName("HeaderGear")
        self._gear.setIcon(QIcon(lucide_pixmap("settings", size=12, color=STUDIO_TEXT_DIM)))
        self._gear.setAutoRaise(True)
        header.sectionResized.connect(lambda *_: self._place_gear())
        header.geometriesChanged.connect(self._place_gear)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._place_gear()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_gear()

    def _place_gear(self) -> None:
        header = self.horizontalHeader()
        x = header.sectionViewportPosition(COL_ACTIONS)
        width = header.sectionSize(COL_ACTIONS)
        self._gear.setGeometry(x + max(0, (width - 18) // 2), max(0, (header.height() - 18) // 2), 18, 18)

    def item(self, row: int, column: int) -> _TableItem | None:
        model = self.model()
        if model is None:
            return None
        index = model.index(row, column)
        value = model.data(index, Qt.ItemDataRole.DisplayRole)
        return _TableItem("" if value is None else str(value))


class NameDelegate(QStyledItemDelegate):
    _AVATAR = 22
    _INSET = 8
    _GAP = 5

    def _is_placeholder(self, name: str) -> bool:
        return (
            not name
            or name in {LOADING_PROFILES, EMPTY_PROFILES}
            or name.startswith("No profiles")
        )

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not self._is_placeholder(name):
            option.text = ""
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        super().paint(painter, opt, index)
        if self._is_placeholder(name):
            return
        avatar = paint_initials_avatar(
            self._AVATAR, initials_from_name(name), color=color_for_name(name)
        )
        x = option.rect.x() + self._INSET
        y = option.rect.y() + (option.rect.height() - self._AVATAR) // 2
        painter.save()
        painter.drawPixmap(x, y, avatar)
        painter.setPen(QPen(QColor(STUDIO_TEXT)))
        painter.setFont(studio_font(12))
        text_left = self._INSET + self._AVATAR + self._GAP
        painter.drawText(
            option.rect.adjusted(text_left, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            name,
        )
        painter.restore()


class VisibilityDelegate(QStyledItemDelegate):
    _DOT = 8
    _GAP = 8

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        # super().paint() re-calls this; keep text empty so Qt does not draw
        # "Unlisted" under the status dot.
        option.text = ""
        option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasDisplay

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        super().paint(painter, opt, index)
        raw = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        label = title_visibility(raw)
        color = _VISIBILITY_COLORS.get(visibility_key(raw), STUDIO_WARNING)
        x = option.rect.x() + 8
        y = option.rect.y() + (option.rect.height() - self._DOT) // 2
        painter.save()
        painter.drawPixmap(x, y, visibility_dot(color, self._DOT))
        painter.setPen(QPen(QColor(STUDIO_TEXT)))
        painter.setFont(studio_font(12))
        text_left = 8 + self._DOT + self._GAP
        painter.drawText(
            option.rect.adjusted(text_left, 0, -4, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index):  # noqa: N802
        hint = super().sizeHint(option, index)
        hint.setWidth(max(hint.width(), 96))
        return hint


class ActionsDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        super().paint(painter, opt, index)
        icon = profile_icon("ellipsis-vertical", size=16, color=STUDIO_TEXT_MUTED)
        x = option.rect.x() + (option.rect.width() - 16) // 2
        y = option.rect.y() + (option.rect.height() - 16) // 2
        painter.drawPixmap(x, y, icon)


class ChannelProfilesCard(StudioPanel):
    def __init__(self, parent: QWidget | None = None, *, api: PlatformApi | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._api = api
        self._user_id = ""
        self._all_profiles: list[ProfileResponse] = []
        self._filtered: list[ProfileResponse] = []
        self._page = 0
        self._allowance_text = "--"
        self._default_id: str | None = None
        self._save_worker: SaveProfileWorker | None = None
        self._delete_worker: DeleteProfileWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("CHANNEL PROFILES")
        title.setObjectName("SectionLabel")
        title.setFont(studio_font(12, uppercase=True, letter_spacing=110))
        left.addWidget(title)
        subtitle = QLabel(PROFILES_SUBTITLE)
        subtitle.setObjectName("SectionHint")
        subtitle.setWordWrap(True)
        left.addWidget(subtitle)
        header.addLayout(left, 1)
        self._allowance = QLabel("--")
        self._allowance.setObjectName("AllowanceLabel")
        header.addWidget(self._allowance, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        toolbar = QWidget()
        toolbar.setObjectName("Toolbar")
        toolbar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(8)

        self._search = QLineEdit()
        self._search.setObjectName("SearchBox")
        self._search.setPlaceholderText("Search profiles...")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(300)
        self._search.setMaximumWidth(360)
        self._search.addAction(
            QIcon(lucide_pixmap("search", size=14, color=STUDIO_TEXT_DIM)),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search.textChanged.connect(self._refilter)
        tools.addWidget(self._search)

        self._visibility = StudioComboBox()
        self._visibility.setObjectName("VisibilityFilter")
        funnel = QIcon(profile_icon("funnel", size=13, color=STUDIO_TEXT_DIM))
        self._visibility.addItem(funnel, "All visibility", "all")
        self._visibility.addItem("Public", "public")
        self._visibility.addItem("Unlisted", "unlisted")
        self._visibility.addItem("Private", "private")
        self._visibility.setMinimumWidth(168)
        self._visibility.currentIndexChanged.connect(self._refilter)
        tools.addWidget(self._visibility)
        tools.addStretch(1)

        self._add = QPushButton("+ Add Profile")
        self._add.setObjectName("TransportPrimary")
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.clicked.connect(self._add_profile)
        self._add.hide()
        tools.addWidget(self._add)
        layout.addWidget(toolbar)

        self._model = ProfileTableModel(self)
        self._table = ProfileTable(self._model)
        self._table.setItemDelegateForColumn(COL_NAME, NameDelegate(self._table))
        self._table.setItemDelegateForColumn(COL_VISIBILITY, VisibilityDelegate(self._table))
        self._table.setItemDelegateForColumn(COL_ACTIONS, ActionsDelegate(self._table))
        layout.addWidget(self._table, 1)

        self._pager = QWidget()
        self._pager.setObjectName("Toolbar")
        pager = QHBoxLayout(self._pager)
        pager.setContentsMargins(0, 0, 0, 0)
        pager.setSpacing(4)
        pager.addStretch(1)
        self._prev = self._make_page_button(
            icon=lucide_pixmap("chevron-left", size=14, color=STUDIO_TEXT)
        )
        self._prev.clicked.connect(lambda: self._set_page(self._page - 1))
        pager.addWidget(self._prev)
        self._page_buttons: list[QPushButton] = []
        self._page_host = QHBoxLayout()
        self._page_host.setSpacing(4)
        pager.addLayout(self._page_host)
        self._next = self._make_page_button(
            icon=lucide_pixmap("chevron-right", size=14, color=STUDIO_TEXT)
        )
        self._next.clicked.connect(lambda: self._set_page(self._page + 1))
        pager.addWidget(self._next)
        self._pager.hide()
        layout.addWidget(self._pager)

    def _make_page_button(self, text: str = "", *, icon=None) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("PageButton")
        button.setFixedSize(22, 22)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if icon is not None:
            button.setIcon(QIcon(icon))
            button.setIconSize(QSize(14, 14))
            button.setText("")
        return button

    def show_loading(self, allowance: str = "--") -> None:
        self._allowance_text = allowance
        self._allowance.setText(allowance)
        self._all_profiles = []
        self._filtered = []
        self._page = 0
        self._model.set_placeholder(LOADING_PROFILES)
        self._refresh_pager()

    def show_empty(self, allowance: str = "0") -> None:
        self._allowance_text = allowance
        self._allowance.setText(allowance)
        self._all_profiles = []
        self._filtered = []
        self._page = 0
        self._model.set_placeholder(EMPTY_PROFILES)
        self._refresh_pager()

    def apply(self, data: DashboardOverview) -> None:
        me = data.me
        self._user_id = me.id
        profiles = list(data.profiles)
        allowance = (
            f"{me.channel_profile_count} / {me.effective_profile_allowance or me.profile_allowance}"
            if me.effective_profile_allowance is not None or me.profile_allowance is not None
            else str(len(profiles))
        )
        self._allowance_text = allowance
        self._allowance.setText(allowance)
        self._all_profiles = profiles
        self._page = 0
        self._refilter()

    def _refilter(self) -> None:
        query = self._search.text().strip().lower()
        visibility = str(self._visibility.currentData() or "all")
        rows: list[ProfileResponse] = []
        for profile in self._all_profiles:
            if query and query not in get_profile_search_haystack(profile):
                continue
            if visibility != "all" and visibility_key(profile_visibility(profile)) != visibility:
                continue
            rows.append(profile)
        self._filtered = rows
        page_count = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE) if rows else 1
        self._page = min(self._page, page_count - 1)
        self._render_page()

    def _render_page(self) -> None:
        if not self._all_profiles:
            self._model.set_placeholder(EMPTY_PROFILES)
            self._refresh_pager()
            return
        if not self._filtered:
            self._model.set_placeholder("No profiles match this search.")
            self._refresh_pager()
            return
        start = self._page * PAGE_SIZE
        page_rows = self._filtered[start : start + PAGE_SIZE]
        self._model.set_profiles(page_rows)
        if page_rows:
            self._table.selectRow(0)
        self._refresh_pager()

    def _refresh_pager(self) -> None:
        total = len(self._filtered)
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
        self._pager.setVisible(page_count > 1)
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < page_count - 1)
        while self._page_buttons:
            button = self._page_buttons.pop()
            self._page_host.removeWidget(button)
            button.deleteLater()
        for index in range(page_count):
            button = self._make_page_button(text=str(index + 1))
            button.setCheckable(True)
            button.setChecked(index == self._page)
            button.clicked.connect(lambda _checked=False, page=index: self._set_page(page))
            self._page_host.addWidget(button)
            self._page_buttons.append(button)

    def _set_page(self, page: int) -> None:
        total = len(self._filtered)
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
        self._page = max(0, min(page, page_count - 1))
        self._render_page()

    def _on_cell_clicked(self, index) -> None:
        if index.column() != COL_ACTIONS:
            return
        profile = self._model.profile_at(index.row())
        if profile is None:
            return
        rect = self._table.visualRect(index)
        global_pos = self._table.viewport().mapToGlobal(rect.bottomRight())
        self._open_row_menu(profile, global_pos)

    def _on_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        profile = self._model.profile_at(index.row()) if index.isValid() else None
        if profile is None:
            return
        self._open_row_menu(profile, self._table.viewport().mapToGlobal(pos))

    def _open_row_menu(self, profile: ProfileResponse, global_pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background:{STUDIO_PANEL}; color:{STUDIO_TEXT}; border:1px solid {STUDIO_BORDER_STRONG}; }}"
            "QMenu::item { padding:6px 14px; }"
            "QMenu::item:selected { background: rgba(99,53,217,0.28); }"
        )
        menu.addAction("Edit Profile", lambda: self._edit_profile(profile))
        menu.addAction("Duplicate", lambda: self._duplicate_profile(profile))
        menu.addAction("Open Folder", lambda: self._open_folder(profile))
        menu.addAction("Set as Default", lambda: self._set_default(profile))
        menu.addSeparator()
        delete_action = menu.addAction(
            QIcon(profile_icon("x", size=14, color=STUDIO_WARNING)),
            "Delete",
        )
        delete_action.triggered.connect(lambda: self._delete_profile(profile))
        menu.exec(global_pos)

    def _add_profile(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        if not str(payload.get("name") or "").strip():
            notify_action("Profile name is required.", tone="error")
            return
        self._save_payload(payload, profile_id=None, local=self._local_from_payload(payload))

    def _edit_profile(self, profile: ProfileResponse) -> None:
        dialog = ProfileDialog(self, profile=profile)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        local = profile.model_copy(update=payload)
        self._save_payload(payload, profile_id=profile.id, local=local)

    def _duplicate_profile(self, profile: ProfileResponse) -> None:
        clone = profile.model_copy(
            update={
                "id": f"local-{uuid4().hex[:8]}",
                "name": f"{profile.name} copy",
                "folder_name": f"{profile.folder_name or profile.run_prefix or 'profile'}-copy",
            }
        )
        payload = {
            "name": clone.name,
            "folder_name": clone.folder_name,
            "run_prefix": clone.run_prefix,
            "output_resolution": clone.output_resolution,
            "image_config": clone.image_config,
            "youtube_config": clone.youtube_config,
        }
        self._save_payload(payload, profile_id=None, local=clone)

    def _open_folder(self, profile: ProfileResponse) -> None:
        base = get_user_workspace_dir(self._user_id or None)
        folder = (profile.folder_name or profile.run_prefix or "").strip()
        target = base / folder if folder else base
        path = target if target.exists() else base
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        notify_action(f"Opened {path.name}.", tone="neutral")

    def _set_default(self, profile: ProfileResponse) -> None:
        self._default_id = profile.id
        notify_action(f"{profile.name} set as the default profile.", tone="success")

    def _delete_profile(self, profile: ProfileResponse) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Delete profile")
        box.setText(f'Delete "{profile.name}"? This cannot be undone.')
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setStyleSheet(
            "QMessageBox { background:#071426; color:#E5EDF7; }"
            "QLabel { color:#E5EDF7; }"
            "QPushButton { min-height:26px; padding:0 12px; background:#101F32; color:#E5EDF7; border:1px solid #23415E; border-radius:5px; }"
        )
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        if self._api is not None:
            worker = DeleteProfileWorker(self._api, profile.id, self)
            worker.succeeded.connect(lambda _result, item=profile: self._remove_local(item))
            worker.failed.connect(lambda message, item=profile: self._delete_failed(message, item))
            self._delete_worker = worker
            worker.start()
            return
        self._remove_local(profile)

    def _delete_failed(self, message: str, profile: ProfileResponse) -> None:
        notify_action(str(message or "Could not delete on the server. Removed locally."), tone="error")
        self._remove_local(profile)

    def _remove_local(self, profile: ProfileResponse) -> None:
        self._all_profiles = [item for item in self._all_profiles if item.id != profile.id]
        self._refilter()
        notify_action(f"Deleted {profile.name}.", tone="success")

    def _save_payload(
        self,
        payload: dict[str, object],
        *,
        profile_id: str | None,
        local: ProfileResponse,
    ) -> None:
        if self._api is not None:
            worker = SaveProfileWorker(self._api, profile_id=profile_id, payload=payload, parent=self)
            worker.succeeded.connect(self._replace_or_insert)
            worker.failed.connect(lambda message, item=local: self._save_failed(message, item))
            self._save_worker = worker
            worker.start()
            return
        self._replace_or_insert(local)

    def _save_failed(self, message: str, local: ProfileResponse) -> None:
        notify_action(str(message or "Saved locally only."), tone="error")
        self._replace_or_insert(local)

    def _replace_or_insert(self, payload: object) -> None:
        if not isinstance(payload, ProfileResponse):
            return
        replaced = False
        next_rows: list[ProfileResponse] = []
        for item in self._all_profiles:
            if item.id == payload.id or item.name == payload.name:
                next_rows.append(payload)
                replaced = True
            else:
                next_rows.append(item)
        if not replaced:
            next_rows.insert(0, payload)
        self._all_profiles = next_rows
        self._refilter()
        notify_action(f"Saved {payload.name}.", tone="success")

    def _local_from_payload(self, payload: dict[str, object]) -> ProfileResponse:
        return ProfileResponse(
            id=f"local-{uuid4().hex[:8]}",
            user_id=self._user_id or "local",
            name=str(payload.get("name") or "Untitled"),
            folder_name=str(payload.get("folder_name") or "") or None,
            run_prefix=str(payload.get("run_prefix") or "") or None,
            output_resolution=str(payload.get("output_resolution") or "1920x1080"),
            image_config=payload.get("image_config") if isinstance(payload.get("image_config"), dict) else None,
            youtube_config=payload.get("youtube_config") if isinstance(payload.get("youtube_config"), dict) else None,
        )
