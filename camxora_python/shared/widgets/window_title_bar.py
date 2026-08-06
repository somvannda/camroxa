"""Custom frameless window title bar matching the CAMXORA studio chrome."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QPoint, Qt
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from shared.icons.chrome_assets import CHROME_SVG_BY_NAME
from shared.lib.resource_paths import get_resource_path
from shared.widgets.setup_notification import SetupNotificationButton


def _read_chrome_svg(name: str) -> str:
    """Load a chrome SVG from packaged resources, with embedded fallback."""
    path = get_resource_path(name)
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return CHROME_SVG_BY_NAME.get(name, "")


def _render_svg_pixmap(raw_svg: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not raw_svg.strip():
        return pixmap
    renderer = QSvgRenderer(QByteArray(raw_svg.encode("utf-8")))
    if not renderer.isValid():
        return pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def _load_logo_pixmap(size: int) -> QPixmap:
    return _render_svg_pixmap(_read_chrome_svg("app-logo.svg"), size)


def _load_icon_pixmap(name: str, *, size: int, color: str) -> QPixmap:
    raw_svg = _read_chrome_svg(name).replace("currentColor", color)
    return _render_svg_pixmap(raw_svg, size)


class WindowControlButton(QPushButton):
    """Minimal icon-only window control button (also reused for compact list ×)."""

    def __init__(
        self,
        kind: str,
        parent: QWidget | None = None,
        *,
        width: int = 40,
        height: int = 32,
        icon_size: int = 16,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._icon_size = max(8, int(icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setFixedSize(max(16, int(width)), max(16, int(height)))

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        background = QColor(0, 0, 0, 0)
        if self._kind == "close":
            if self.isDown():
                background = QColor(244, 63, 94, 70)
            elif self.underMouse():
                background = QColor(244, 63, 94, 51)
        else:
            if self.isDown():
                background = QColor(255, 255, 255, 20)
            elif self.underMouse():
                background = QColor(255, 255, 255, 13)

        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            radius = 4 if min(self.width(), self.height()) <= 24 else 6
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), radius, radius)

        icon_color = "#cbd5e1"
        if self._kind == "close" and self.underMouse():
            icon_color = "#fecdd3"
        elif self.underMouse():
            icon_color = "#ffffff"

        icon_name = {
            "minimize": "window-minimize.svg",
            "maximize": "window-maximize.svg",
            "close": "window-close.svg",
        }[self._kind]
        icon = _load_icon_pixmap(icon_name, size=self._icon_size, color=icon_color)
        x = (self.width() - icon.width()) // 2
        y = (self.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)


# Backward-compatible alias used by interactive-child checks / older imports.
_WindowControlButton = WindowControlButton


class WindowTitleBar(QFrame):
    """Custom desktop header with brand lockup and window controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("window_title_bar")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(56)
        self._drag_offset: QPoint | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("window_brand_logo")
        logo.setPixmap(_load_logo_pixmap(32))
        logo.setFixedSize(32, 32)
        root.addWidget(logo, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)

        title = QLabel("CAMXORA")
        title.setObjectName("window_brand_title")
        title_font = QFont(title.font())
        title_font.setFamilies(["Inter", "Segoe UI", "Arial"])
        title_font.setWeight(QFont.Weight.DemiBold)
        title_font.setPointSizeF(14)
        title_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 118)
        title.setFont(title_font)
        title_col.addWidget(title)

        subtitle = QLabel("FACELESS DESKTOP STUDIO")
        subtitle.setObjectName("window_brand_subtitle")
        subtitle_font = QFont(subtitle.font())
        subtitle_font.setFamilies(["Inter", "Segoe UI", "Arial"])
        subtitle_font.setCapitalization(QFont.Capitalization.AllUppercase)
        subtitle_font.setPointSizeF(11)
        subtitle_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 120)
        subtitle.setFont(subtitle_font)
        title_col.addWidget(subtitle)

        root.addLayout(title_col)
        root.addStretch(1)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(4)

        self._setup_notifications = SetupNotificationButton(self)
        self._setup_notifications.hide()

        self._minimize_button = _WindowControlButton("minimize", self)
        self._maximize_button = _WindowControlButton("maximize", self)
        self._close_button = _WindowControlButton("close", self)

        self._minimize_button.clicked.connect(self._minimize_window)
        self._maximize_button.clicked.connect(self._toggle_maximize)
        self._close_button.clicked.connect(self._close_window)

        controls.addWidget(self._setup_notifications)
        controls.addWidget(self._minimize_button)
        controls.addWidget(self._maximize_button)
        controls.addWidget(self._close_button)
        root.addLayout(controls)

    def set_setup_notifications_visible(self, visible: bool) -> None:
        self._setup_notifications.setVisible(visible)

    @staticmethod
    def _is_interactive_child(widget: QWidget | None) -> bool:
        while widget is not None:
            if isinstance(widget, (_WindowControlButton, SetupNotificationButton)):
                return True
            widget = widget.parentWidget()
        return False

    def sync_window_state(self) -> None:
        """Reserved for parity with RootWindow state syncing."""
        return

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and not self._is_interactive_child(
            self.childAt(event.position().toPoint()),
        ):
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        child = self.childAt(event.position().toPoint())
        if self._is_interactive_child(child):
            super().mousePressEvent(event)
            return

        window = self.window()
        handle = window.windowHandle() if isinstance(window, QWidget) else None
        if handle is not None and not window.isMaximized():
            try:
                handle.startSystemMove()
                event.accept()
                return
            except Exception:
                pass

        if isinstance(window, QWidget) and not window.isMaximized():
            self._drag_offset = event.globalPosition().toPoint() - window.frameGeometry().topLeft()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        window = self.window()
        if (
            self._drag_offset is not None
            and isinstance(window, QWidget)
            and not window.isMaximized()
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def _minimize_window(self) -> None:
        window = self.window()
        if isinstance(window, QWidget):
            window.showMinimized()

    def _toggle_maximize(self) -> None:
        window = self.window()
        if not isinstance(window, QWidget):
            return
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()
        self.sync_window_state()

    def _close_window(self) -> None:
        window = self.window()
        if isinstance(window, QWidget):
            window.close()
