"""Header notification bell with badge and notification panel dropdown."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from shared.icons.lucide_icons import lucide_pixmap
from shared.lib.music_readiness import MusicReadinessReport
from shared.models.notification_item import (
    NotificationItem,
    format_notification_timestamp,
    group_notifications,
    notification_item_from_push,
    notification_item_from_setup,
    notification_sort_key,
)
from shared.models.push_events import SOFTWARE_UPDATE_AVAILABLE
from shared.services.push_notification_hub import PushNotificationHub
from shared.services.setup_readiness_service import SetupReadinessService
from shared.services.software_update_service import SoftwareUpdateService

PANEL_WIDTH = 440
PANEL_HEIGHT = 520
PANEL_CORNER_RADIUS = 12
ICON_BADGE_SIZE = 42
ICON_BADGE_COLOR = "#1a3a5c"
ICON_BADGE_BORDER = "#2d4f73"
NOTIFICATION_ROW_HEIGHT = 108


class _NotificationBadge(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def set_count(self, count: int) -> None:
        if count <= 0:
            self.hide()
            return
        self.setText(str(count if count < 100 else "99+"))
        self.show()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ef4444"))
        painter.drawEllipse(self.rect())
        painter.setPen(QColor("#ffffff"))
        font = QFont(self.font())
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


class _IconCircle(QWidget):
    def __init__(self, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self.setFixedSize(ICON_BADGE_SIZE, ICON_BADGE_SIZE)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor(ICON_BADGE_BORDER))
        painter.setBrush(QColor(ICON_BADGE_COLOR))
        painter.drawEllipse(1, 1, self.width() - 2, self.height() - 2)
        icon = lucide_pixmap(self._icon_name, size=18, color="#dbeafe")
        x = (self.width() - icon.width()) // 2
        y = (self.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)


class _GhostIconButton(QPushButton):
    def __init__(self, icon_name: str, *, tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setFixedSize(28, 28)
        if tooltip:
            self.setToolTip(tooltip)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.underMouse() or self.isDown():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 18 if self.isDown() else 10))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 6, 6)
        color = "#e2e8f0" if self.underMouse() else "#94a3b8"
        icon = lucide_pixmap(self._icon_name, size=14, color=color)
        x = (self.width() - icon.width()) // 2
        y = (self.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)


class _NotificationDivider(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("notification_divider")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)


class _NotificationRow(QWidget):
    dismiss_requested = Signal(str)
    action_requested = Signal(str)

    def __init__(self, item: NotificationItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = item
        self._hovered = False
        self.setObjectName("notification_row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 12, 4, 12)
        layout.setSpacing(14)

        self.setFixedHeight(NOTIFICATION_ROW_HEIGHT)

        self._icon = _IconCircle(item.icon, self)
        layout.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        title = QLabel(item.title, self)
        title.setObjectName("notification_item_title")
        title.setWordWrap(False)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_col.addWidget(title)

        message = QLabel(item.message, self)
        message.setObjectName("notification_item_message")
        message.setWordWrap(True)
        message.setMaximumHeight(36)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_col.addWidget(message)

        timestamp = QLabel(format_notification_timestamp(item.created_at), self)
        timestamp.setObjectName("notification_item_timestamp")
        text_col.addWidget(timestamp)
        text_col.addStretch(1)

        if item.primary_action:
            self._action_btn = QPushButton(item.primary_action, self)
            self._action_btn.setObjectName("notification_action_button")
            self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._action_btn.clicked.connect(lambda: self.action_requested.emit(item.id))
            text_col.addWidget(self._action_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            self._action_btn = None

        self._message_label = message

        layout.addLayout(text_col, stretch=1)

        action_widgets: list[QWidget] = [self._icon, title, message, timestamp]
        if item.can_dismiss:
            self._remove_btn = _GhostIconButton("x", tooltip="Remove notification", parent=self)
            self._remove_btn.clicked.connect(lambda: self.dismiss_requested.emit(item.id))
            layout.addWidget(self._remove_btn, alignment=Qt.AlignmentFlag.AlignTop)
            action_widgets.append(self._remove_btn)
        else:
            self._remove_btn = None

        for child in action_widgets:
            if item.primary_action and child.objectName() == "notification_action_button":
                continue
            child.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            child.setMouseTracking(True)
            child.installEventFilter(self)
        if item.primary_action:
            self._action_btn.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            self._action_btn.setMouseTracking(True)
            self._action_btn.installEventFilter(self)

    def set_install_status(self, message: str, *, in_progress: bool) -> None:
        self._message_label.setText(message)
        if self._action_btn is not None:
            self._action_btn.setEnabled(not in_progress)

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave, QEvent.Type.HoverEnter, QEvent.Type.HoverLeave):
            self._sync_hover_state()
        return super().eventFilter(watched, event)

    def enterEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._sync_hover_state()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        self._sync_hover_state()
        super().leaveEvent(event)

    def _sync_hover_state(self) -> None:
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        hovered = self.rect().contains(local_pos)
        if hovered != self._hovered:
            self._hovered = hovered
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if hovered else Qt.CursorShape.ArrowCursor
            )
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        if self._hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QColor(255, 255, 255, 22))
            painter.setBrush(QColor(255, 255, 255, 12))
            painter.drawRoundedRect(self.rect().adjusted(0, 2, 0, -2), 8, 8)
        super().paintEvent(_event)


class _NotificationDropdown(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self.setObjectName("setup_notification_dropdown")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(PANEL_WIDTH, PANEL_HEIGHT)

        self._on_dismiss: Callable[[str], None] | None = None
        self._on_action: Callable[[str], None] | None = None
        self._rows_by_id: dict[str, _NotificationRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 16, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(4)

        self._title = QLabel("Notification")
        self._title.setObjectName("notification_panel_title")
        title_col.addWidget(self._title)

        self._subtitle = QLabel("You have 0 notifications today.")
        self._subtitle.setObjectName("notification_panel_subtitle")
        self._subtitle.setWordWrap(True)
        title_col.addWidget(self._subtitle)

        header.addLayout(title_col, stretch=1)

        close_btn = _GhostIconButton("x", tooltip="Close", parent=self)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        root.addSpacing(16)
        root.addWidget(_NotificationDivider(self))
        root.addSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("notification_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setMinimumHeight(360)
        corner = QWidget(self._scroll)
        corner.setFixedSize(0, 0)
        self._scroll.setCornerWidget(corner)
        self._scroll.viewport().setAutoFillBackground(False)

        self._list_host = QWidget()
        self._list_host.setObjectName("notification_list_host")
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(0, 4, 0, 4)
        self._list_layout.setSpacing(0)
        self._scroll.setWidget(self._list_host)
        root.addWidget(self._scroll)

        self._empty_label = QLabel("You're all caught up.")
        self._empty_label.setObjectName("notification_empty_state")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.hide()
        root.addWidget(self._empty_label)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_rounded_mask()
        self._disable_platform_shadow()
        super().showEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._apply_rounded_mask()
        super().resizeEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#1e3a5f"))
        painter.setBrush(QColor("#0b1228"))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), PANEL_CORNER_RADIUS, PANEL_CORNER_RADIUS)

    def _disable_platform_shadow(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            if hwnd == 0:
                return
            policy = ctypes.c_int(1)  # DWMNCRP_DISABLED
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                2,
                ctypes.byref(policy),
                ctypes.sizeof(policy),
            )
        except Exception:
            return

    def _apply_rounded_mask(self) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), PANEL_CORNER_RADIUS, PANEL_CORNER_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def set_dismiss_handler(self, handler: Callable[[str], None]) -> None:
        self._on_dismiss = handler

    def set_action_handler(self, handler: Callable[[str], None]) -> None:
        self._on_action = handler

    def apply(self, items: list[NotificationItem]) -> None:
        self._rows_by_id.clear()
        while self._list_layout.count():
            child = self._list_layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()

        today_count = sum(1 for item in items if item.created_at.astimezone().date() == date.today())
        total = len(items)
        if today_count == total:
            if today_count == 1:
                self._subtitle.setText("You have 1 notification today.")
            else:
                self._subtitle.setText(f"You have {today_count} notifications today.")
        elif total == 1:
            self._subtitle.setText("You have 1 open notification.")
        else:
            self._subtitle.setText(f"You have {total} open notifications.")

        if not items:
            self._scroll.hide()
            self._empty_label.show()
            return

        self._empty_label.hide()
        self._scroll.show()

        grouped = group_notifications(items)
        for group_index, (group_label, group_items) in enumerate(grouped):
            if group_index > 0:
                self._list_layout.addSpacing(14)
            section = QLabel(group_label)
            section.setObjectName("notification_group_title")
            self._list_layout.addWidget(section)
            self._list_layout.addSpacing(4)

            for item_index, item in enumerate(group_items):
                row = _NotificationRow(item, self._list_host)
                row.dismiss_requested.connect(self._handle_dismiss)
                row.action_requested.connect(self._handle_action)
                self._list_layout.addWidget(row)
                self._rows_by_id[item.id] = row
                if item_index < len(group_items) - 1:
                    self._list_layout.addSpacing(2)
                    self._list_layout.addWidget(_NotificationDivider(self._list_host))
                    self._list_layout.addSpacing(2)

        self._list_layout.addStretch(1)
        self._apply_rounded_mask()

    def set_install_status(self, notification_id: str, message: str, *, in_progress: bool) -> None:
        row = self._rows_by_id.get(notification_id)
        if row is not None:
            row.set_install_status(message, in_progress=in_progress)

    def _handle_dismiss(self, notification_id: str) -> None:
        if self._on_dismiss is not None:
            self._on_dismiss(notification_id)

    def _handle_action(self, notification_id: str) -> None:
        if self._on_action is not None:
            self._on_action(notification_id)


class _SetupBellButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setFixedSize(40, 32)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        background = QColor(0, 0, 0, 0)
        if self.isDown():
            background = QColor(255, 255, 255, 20)
        elif self.underMouse():
            background = QColor(255, 255, 255, 13)
        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)
        icon_color = "#ffffff" if self.underMouse() else "#cbd5e1"
        icon = lucide_pixmap("bell", size=16, color=icon_color)
        x = (self.width() - icon.width()) // 2
        y = (self.height() - icon.height()) // 2
        painter.drawPixmap(x, y, icon)


class SetupNotificationButton(QWidget):
    """Bell icon with badge count and notification dropdown."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dropdown = _NotificationDropdown(self)
        self._dropdown.hide()
        self._dropdown.set_dismiss_handler(self._dismiss_notification)
        self._dropdown.set_action_handler(self._run_notification_action)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)

        self._button = _SetupBellButton(self)
        self._button.clicked.connect(self._toggle_dropdown)
        layout.addWidget(self._button)

        self._badge = _NotificationBadge(self._button)
        self._badge.move(22, 2)

        service = SetupReadinessService.instance()
        service.report_changed.connect(self._rebuild_notifications)

        hub = PushNotificationHub.instance()
        hub.inbox_changed.connect(self._rebuild_notifications)
        self._rebuild_notifications()

        self._active_update_notification_id: str | None = None
        update_service = SoftwareUpdateService.instance()
        update_service.install_started.connect(self._on_update_install_started)
        update_service.install_progress.connect(self._on_update_install_progress)
        update_service.install_failed.connect(self._on_update_install_failed)

    def _resolve_update_notification_id(self) -> str | None:
        if self._active_update_notification_id:
            return self._active_update_notification_id
        pending = SoftwareUpdateService.instance().pending
        if pending is not None and pending.notification_id:
            return pending.notification_id
        for item in self._collect_notifications():
            if item.event == SOFTWARE_UPDATE_AVAILABLE:
                return item.id
        return None

    def _on_update_install_started(self) -> None:
        notification_id = self._resolve_update_notification_id()
        if notification_id is None:
            return
        self._dropdown.set_install_status(
            notification_id,
            "Preparing update…",
            in_progress=True,
        )

    def _on_update_install_progress(self, message: str, percent: int = -1) -> None:
        del percent
        notification_id = self._resolve_update_notification_id()
        if notification_id is None:
            return
        self._dropdown.set_install_status(notification_id, message, in_progress=True)

    def _on_update_install_failed(self, message: str) -> None:
        notification_id = self._resolve_update_notification_id()
        if notification_id is None:
            return
        self._dropdown.set_install_status(notification_id, message, in_progress=False)
        self._active_update_notification_id = None

    def paint_notification_icon(self) -> None:
        self._button.update()

    def _collect_notifications(self) -> list[NotificationItem]:
        hub = PushNotificationHub.instance()
        notifications: list[NotificationItem] = []

        report = SetupReadinessService.instance().report
        if isinstance(report, MusicReadinessReport):
            for item in report.items:
                if item.complete:
                    continue
                setup_item = notification_item_from_setup(item)
                if hub.is_dismissed(setup_item.id):
                    continue
                notifications.append(setup_item)

        for push_item in hub.inbox_items:
            if hub.is_dismissed(push_item.id):
                continue
            notifications.append(notification_item_from_push(push_item))

        notifications.sort(key=notification_sort_key)
        return notifications

    def _rebuild_notifications(self) -> None:
        items = self._collect_notifications()
        self._dropdown.apply(items)
        self._badge.set_count(len(items))

    def _dismiss_notification(self, notification_id: str) -> None:
        PushNotificationHub.instance().dismiss(notification_id)
        self._rebuild_notifications()

    def _run_notification_action(self, notification_id: str) -> None:
        for item in self._collect_notifications():
            if item.id != notification_id:
                continue
            if item.event == SOFTWARE_UPDATE_AVAILABLE:
                self._active_update_notification_id = notification_id
                SoftwareUpdateService.instance().start_install(parent=self)
            break

    def _toggle_dropdown(self) -> None:
        if self._dropdown.isVisible():
            self._dropdown.hide()
            return
        self._rebuild_notifications()
        # Anchor the panel under the bell, flush to the right edge of the button.
        global_pos = self._button.mapToGlobal(QPoint(0, self._button.height() + 4))
        dropdown_x = global_pos.x() + self._button.width() - self._dropdown.width()
        self._dropdown.move(max(8, dropdown_x), global_pos.y())
        self._dropdown.show()
        self._dropdown.raise_()
        self._dropdown.activateWindow()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._badge.move(22, 2)
        super().resizeEvent(event)
