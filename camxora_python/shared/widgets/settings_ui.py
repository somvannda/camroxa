"""Standard settings layout helpers — account_card panels matching Electron structure."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shared.themes.badge_pills import apply_badge_pill, status_pill_object_name
from shared.themes.deep_blue import (
    MUSIC_SECTION_ID,
    PANEL_SCROLL_AREA_ID,
    PANEL_SCROLL_CONTENT_ID,
    PANEL_SCROLL_RIGHT_GUTTER_PX,
    PROFILE_IDENTITY_AVATAR_ID,
    PROFILE_IDENTITY_STRIP_ID,
    SETTINGS_FORM_ROW_ID,
    SETTINGS_PATH_ROW_ID,
    SETTINGS_SECONDARY_BUTTON_ID,
    SUBTITLE_LABEL_ID,
)


class SettingsPanel(QFrame):
    """account_card with title + optional subtitle + content area."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        pin_content_top: bool = False,
        fill_available_height: bool = False,
        expand_vertically: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        fill_available_height = fill_available_height or expand_vertically
        super().__init__(parent)
        self.setObjectName("account_card")
        if fill_available_height:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(16, 16, 16, 16)
        self._root.setSpacing(12)

        header = QHBoxLayout()
        text = QVBoxLayout()
        if title:
            title_label = QLabel(title)
            title_label.setObjectName(SUBTITLE_LABEL_ID)
            text.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName(SUBTITLE_LABEL_ID)
            sub.setWordWrap(True)
            text.addWidget(sub)
        header.addLayout(text, stretch=1)
        self._actions_host = QHBoxLayout()
        header.addLayout(self._actions_host)
        # Headerless panels skip the header row entirely (no dead space);
        # add_action attaches it on demand.
        self._header = header
        self._header_attached = bool(title or subtitle)
        if self._header_attached:
            self._root.addLayout(header)

        self._body = QVBoxLayout()
        self._body.setSpacing(8)
        if pin_content_top:
            self._body.setAlignment(Qt.AlignmentFlag.AlignTop)
        if fill_available_height:
            self._root.addLayout(self._body, stretch=1)
        else:
            self._root.addLayout(self._body)

    def add_action(self, widget: QWidget) -> None:
        if not self._header_attached:
            self._root.insertLayout(0, self._header)
            self._header_attached = True
        self._actions_host.addWidget(widget)

    def add_widget(self, widget: QWidget, *, stretch: int = 0) -> None:
        self._body.addWidget(widget, stretch)

    def add_layout(self, layout) -> None:
        self._body.addLayout(layout)

    def add_stretch(self) -> None:
        self._body.addStretch()

    def add_scrolled_section(self) -> QVBoxLayout:
        """Scrollable body region that fills remaining panel height."""
        form_host = QWidget()
        form_host.setObjectName(PANEL_SCROLL_CONTENT_ID)
        form_host.setAutoFillBackground(False)
        form_layout = QVBoxLayout(form_host)
        form_layout.setContentsMargins(0, 0, PANEL_SCROLL_RIGHT_GUTTER_PX, 0)
        form_layout.setSpacing(8)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = make_panel_scroll_area()
        scroll.setWidget(form_host)
        self.add_widget(scroll, stretch=1)
        return form_layout


def form_row(label: str, widget: QWidget) -> QWidget:
    host = QWidget()
    host.setObjectName(SETTINGS_FORM_ROW_ID)
    host.setAutoFillBackground(False)
    grid = QGridLayout(host)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setColumnStretch(1, 1)
    name = QLabel(label)
    name.setObjectName(SUBTITLE_LABEL_ID)
    name.setMinimumWidth(150)
    grid.addWidget(name, 0, 0, Qt.AlignmentFlag.AlignTop)
    grid.addWidget(widget, 0, 1)
    return host


def path_row(
    *,
    line_edit: QLineEdit,
    on_browse,
    on_open,
    browse_label: str = "Browse",
    open_label: str = "Open",
    extra_widgets: list[QWidget] | None = None,
) -> QWidget:
    # QPushButton.clicked emits a checked:bool. Callables that accept one arg
    # (e.g. lambda f=field: ...) would bind that bool and break. Ignore it.
    def _ignore_checked(callback):
        return lambda *_args, _cb=callback: _cb()

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(line_edit, stretch=1)
    browse = QPushButton(browse_label)
    browse.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
    browse.clicked.connect(_ignore_checked(on_browse))
    open_btn = QPushButton(open_label)
    open_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
    open_btn.clicked.connect(_ignore_checked(on_open))
    row.addWidget(browse)
    row.addWidget(open_btn)
    for widget in extra_widgets or ():
        row.addWidget(widget)
    host = QWidget()
    host.setObjectName(SETTINGS_PATH_ROW_ID)
    host.setAutoFillBackground(False)
    host.setLayout(row)
    return host


def mini_stat(label: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("music_section")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(10, 8, 10, 8)
    heading = QLabel(label.upper())
    heading.setObjectName(SUBTITLE_LABEL_ID)
    text = QLabel(value)
    layout.addWidget(heading)
    layout.addWidget(text)
    return frame


def note_box(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(SUBTITLE_LABEL_ID)
    label.setWordWrap(True)
    return label


class ProfileIdentityCard(QFrame):
    """Profile summary strip — subtle border on the card surface, no nested panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(PROFILE_IDENTITY_STRIP_ID)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        avatar_frame = QFrame()
        avatar_frame.setFixedSize(48, 48)
        avatar_frame.setObjectName(PROFILE_IDENTITY_AVATAR_ID)
        avatar_layout = QVBoxLayout(avatar_frame)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        self._initials = QLabel("P")
        self._initials.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(self._initials)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self._channel_title = QLabel("Profile")
        self._source_label = QLabel("Source: Account profile")
        self._source_label.setObjectName(SUBTITLE_LABEL_ID)
        youtube_row = QHBoxLayout()
        youtube_row.setContentsMargins(0, 0, 0, 0)
        youtube_row.setSpacing(6)
        self._youtube_caption = QLabel("YouTube:")
        self._youtube_caption.setObjectName(SUBTITLE_LABEL_ID)
        self._youtube_status = QLabel("Not connected")
        self._youtube_status.setObjectName(SUBTITLE_LABEL_ID)
        youtube_row.addWidget(self._youtube_caption)
        youtube_row.addWidget(self._youtube_status)
        youtube_row.addStretch()
        text_col.addWidget(self._channel_title)
        text_col.addWidget(self._source_label)
        text_col.addLayout(youtube_row)

        layout.addWidget(avatar_frame)
        layout.addLayout(text_col, stretch=1)

    def set_identity(
        self,
        *,
        initials: str,
        channel_title: str,
        source_text: str,
        youtube_status_text: str,
        youtube_connected: bool,
    ) -> None:
        self._initials.setText(initials)
        self._channel_title.setText(channel_title)
        self._source_label.setText(source_text)
        if youtube_connected:
            # Must go through apply_badge_pill so contentsMargins (14×3) land;
            # bare setObjectName(status_pill_success) left Connected flush to edges.
            apply_badge_pill(
                self._youtube_status,
                status_pill_object_name(youtube_status_text),
                label=youtube_status_text,
            )
        else:
            self._youtube_status.setText(youtube_status_text)
            self._youtube_status.setObjectName(SUBTITLE_LABEL_ID)
            self._youtube_status.setContentsMargins(0, 0, 0, 0)
            self._youtube_status.setMinimumWidth(0)
            self._youtube_status.setMaximumWidth(16777215)
            self._youtube_status.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
            )
            self._youtube_status.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            style = self._youtube_status.style()
            if style is not None:
                style.unpolish(self._youtube_status)
                style.polish(self._youtube_status)
            self._youtube_status.updateGeometry()



def two_column_row(
    left: QWidget,
    right: QWidget,
    *,
    left_stretch: int = 1,
    right_stretch: int = 1,
    align_top: bool = False,
) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    alignment = Qt.AlignmentFlag.AlignTop if align_top else Qt.AlignmentFlag()
    row.addWidget(left, left_stretch, alignment)
    row.addWidget(right, right_stretch, alignment)
    return row


def make_panel_scroll_area() -> QScrollArea:
    scroll = QScrollArea()
    scroll.setObjectName(PANEL_SCROLL_AREA_ID)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    scroll.setAutoFillBackground(False)
    scroll.viewport().setAutoFillBackground(False)
    return scroll


def make_fill_tab_page(content: QWidget) -> QWidget:
    """Tab page that consumes all height between tabs and the settings footer."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout.addWidget(content, stretch=1)
    return page


def make_two_column_fill_tab(
    left: QWidget,
    right: QWidget,
    *,
    left_stretch: int = 1,
    right_stretch: int = 1,
) -> QWidget:
    """Two equal-height panels that fill the workspace between tabs and footer."""
    content = QWidget()
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addLayout(
        two_column_row(left, right, left_stretch=left_stretch, right_stretch=right_stretch),
        stretch=1,
    )
    return make_fill_tab_page(content)


def make_scrollable_tab_page(content: QWidget) -> QWidget:
    """Tab page with internal scroll only — outer settings layout never scrolls."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    scroll = make_panel_scroll_area()
    host = QWidget()
    host.setObjectName(PANEL_SCROLL_CONTENT_ID)
    host.setAutoFillBackground(False)
    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, PANEL_SCROLL_RIGHT_GUTTER_PX, 0)
    host_layout.setSpacing(0)
    content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    host_layout.addWidget(content)
    scroll.setWidget(host)
    layout.addWidget(scroll, stretch=1)
    return page
