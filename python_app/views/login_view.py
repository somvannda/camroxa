"""Login and Registration view for the desktop application.

Enterprise-style split-panel auth screen: a purple brand panel on the left
and a focused form panel on the right. Uses the unified style system with
property selectors exclusively — no inline setStyleSheet() calls.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QToolButton,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap, QPalette, QColor, QPainter
from PyQt6.QtSvg import QSvgRenderer

from python_app.app.resources import icon_path, lucide_icon_path
from python_app.design_system.tokens import DEFAULT_DARK_THEME
from python_app.design_system.layouts.master_template import (
    heading_h1,
    text_body,
    text_secondary,
    text_muted,
    text_label,
    text_link,
    input_field,
    button_primary,
    button_secondary,
    form_group,
)
from python_app.views.helpers.style_helper import (
    set_panel_role,
    set_button_role,
    set_label_role,
    set_field_role,
    render_svg_icon,
)


# Design tokens for layout sizing only (no inline QSS)
_COLORS = DEFAULT_DARK_THEME.colors
_TYPOGRAPHY = DEFAULT_DARK_THEME.typography
_SPACING = DEFAULT_DARK_THEME.spacing

# Form column width — constrained so the form feels intentional, not stretched
_FORM_WIDTH = 380

# Vertical spacing scale (8px grid)
_GAP_FIELD = 20      # between stacked fields
_GAP_LABEL = 8       # between a label and its input
_INPUT_HEIGHT = 48
_TAB_HEIGHT = 46
_BUTTON_HEIGHT = 54


def _render_colored_svg(path: str, size: int) -> QPixmap:
    """Render an SVG preserving its own colors (gradients, etc.) to a pixmap."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(path))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


class LoginView(QWidget):
    """Login/Registration view displayed at application startup.

    Signals:
        login_requested(email: str, password: str)
        register_requested(email: str, password: str, display_name: str)
        switch_to_register()
        switch_to_login()
        forgot_password_requested()

    Slots:
        show_error(message: str)
        show_field_errors(errors: dict[str, str])
        show_success(message: str)
        set_loading(is_loading: bool)
    """

    # Signals
    login_requested = pyqtSignal(str, str)
    register_requested = pyqtSignal(str, str, str)
    switch_to_register = pyqtSignal()
    switch_to_login = pyqtSignal()
    forgot_password_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_loading = False
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the split-panel login/register UI."""
        set_panel_role(self, "center")
        self._root = root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._brand_panel = self._build_brand_panel()
        root.addWidget(self._brand_panel, 4)
        root.addWidget(self._build_form_panel(), 6)

    def enter_onboarding_mode(self) -> None:
        """Keep brand panel, hide tab bar/heading — expand form area for onboarding."""
        self._form_stack.setCurrentIndex(0)
        for w in (self._heading_subtitle,):
            w.hide()
        if hasattr(self, '_tab_container'):
            self._tab_container.hide()
        # Collapse the fixed spacers that sat below the (now hidden) heading/tabs
        # so the wizard content starts right under the title (no big gap).
        if hasattr(self, '_sp_after_subtitle'):
            self._sp_after_subtitle.changeSize(0, 0)
        if hasattr(self, '_sp_after_tabs'):
            self._sp_after_tabs.changeSize(0, 0)
        if hasattr(self, '_column') and self._column.layout() is not None:
            self._column.layout().invalidate()
        if hasattr(self, '_column'):
            self._column.setMinimumWidth(0)
            self._column.setMaximumWidth(16777215)
            self._column.setContentsMargins(30, 0, 30, 0)
            self._column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._column.show()
        if hasattr(self, '_title'):
            self._title.setText("Setting Up Your Channel Profiles")
            self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(self, '_message_area'):
            self._message_area.hide()
        # Remove centering stretches to allow full-width expansion
        if hasattr(self, '_center_row'):
            while self._center_row.count():
                item = self._center_row.takeAt(0)
                w = item.widget() if hasattr(item, 'widget') else None
                if w and w != self._column:
                    w.hide()
            self._center_row.addWidget(self._column)
        # Collapse the top/bottom centering stretches so the onboarding content
        # fills the panel vertically (no wasted band at the bottom, scroll area
        # gets the full height so the step fits without scrolling).
        if hasattr(self, '_form_outer'):
            self._form_outer.setStretch(1, 0)  # top stretch
            self._form_outer.setStretch(2, 1)  # center row → expand to fill
            self._form_outer.setStretch(3, 0)  # bottom stretch
            self._form_outer.invalidate()

    def exit_onboarding_mode(self) -> None:
        """Restore brand panel and form to original state."""
        self._brand_panel.show()
        if hasattr(self, '_tab_container'):
            self._tab_container.show()
        if hasattr(self, '_heading_subtitle'):
            self._heading_subtitle.show()
        # Restore the heading/tab spacers for the normal login layout.
        if hasattr(self, '_sp_after_subtitle'):
            self._sp_after_subtitle.changeSize(0, _SPACING.gap_lg, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        if hasattr(self, '_sp_after_tabs'):
            self._sp_after_tabs.changeSize(0, _SPACING.gap_md, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        if hasattr(self, '_column') and self._column.layout() is not None:
            self._column.layout().invalidate()
        if hasattr(self, '_column'):
            self._column.setMinimumWidth(0)
            self._column.setMaximumWidth(16777215)
            self._column.setFixedWidth(_FORM_WIDTH)
            self._column.setContentsMargins(0, 0, 0, 0)
            self._column.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        if hasattr(self, '_title'):
            self._title.setText("Welcome back")
        if hasattr(self, '_message_area'):
            self._message_area.show()
        # Restore centering stretches
        if hasattr(self, '_center_row'):
            while self._center_row.count():
                item = self._center_row.takeAt(0)
                w = item.widget() if hasattr(item, 'widget') else None
                if w and w != self._column:
                    w.deleteLater()
            self._center_row.addStretch(1)
            self._center_row.addWidget(self._column)
            self._center_row.addStretch(1)
        # Restore the outer vertical centering for the normal login screen.
        if hasattr(self, '_form_outer'):
            self._form_outer.setStretch(1, 1)  # top stretch
            self._form_outer.setStretch(2, 0)  # center row (natural height)
            self._form_outer.setStretch(3, 1)  # bottom stretch
            self._form_outer.invalidate()

    def _build_brand_panel(self) -> QWidget:
        """Left panel: purple gradient brand area with logo and value props."""
        panel = QWidget()
        set_panel_role(panel, "brandGradient")
        panel.setMinimumWidth(360)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(56, 56, 56, 56)
        outer.setSpacing(0)
        outer.addStretch(1)

        # Logo + wordmark (left-aligned, side by side)
        brand_row = QWidget()
        brand_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        brand_row_layout = QHBoxLayout(brand_row)
        brand_row_layout.setContentsMargins(0, 0, 0, 0)
        brand_row_layout.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(_render_colored_svg(icon_path("app-logo.svg"), 52))
        logo.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        brand_row_layout.addWidget(logo)

        brand_name = QLabel("CAMXORA")
        set_label_role(brand_name, "loginHeadline")
        _brand_font = brand_name.font()
        _brand_font.setBold(True)
        brand_name.setFont(_brand_font)
        brand_row_layout.addWidget(brand_name, 0, Qt.AlignmentFlag.AlignVCenter)
        brand_row_layout.addStretch(1)

        outer.addWidget(brand_row)
        outer.addSpacing(_SPACING.gap_lg + 4)

        headline = QLabel("Create studio-grade\nmusic videos, automatically.")
        set_label_role(headline, "loginHeadline")
        outer.addWidget(headline)
        outer.addSpacing(_SPACING.gap_md)

        tagline = QLabel(
            "Generate songs, render spectrum videos, and publish to "
            "YouTube — all from one desktop studio."
        )
        tagline.setWordWrap(True)
        set_label_role(tagline, "loginTagline")
        outer.addWidget(tagline)
        outer.addSpacing(_SPACING.gap_lg + 12)

        # Value props
        for icon_name, text in (
            ("music", "AI-powered song & lyric generation"),
            ("video", "Spectrum video rendering"),
            ("workflow", "Batch pipelines & auto-upload"),
        ):
            outer.addWidget(self._build_feature_row(icon_name, text))
            outer.addSpacing(_SPACING.gap_md)

        outer.addStretch(2)
        return panel

    def _build_feature_row(self, icon_name: str, text: str) -> QWidget:
        """A small icon + label row for the brand panel value props."""
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SPACING.gap_md + 2)

        icon = QLabel()
        icon.setFixedSize(QSize(20, 20))
        icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        icon.setPixmap(
            render_svg_icon(lucide_icon_path(icon_name), 20, "#ffffff").pixmap(
                QSize(20, 20)
            )
        )
        layout.addWidget(icon)

        label = QLabel(text)
        set_label_role(label, "loginFeatureText")
        layout.addWidget(label)
        layout.addStretch(1)
        return row

    def _build_form_panel(self) -> QWidget:
        """Right panel: the centered, width-constrained auth form."""
        panel = QWidget()
        set_panel_role(panel, "center")

        self._form_outer = outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Window control buttons at the top-right
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 8, 10, 0)
        controls_row.addStretch(1)

        for icon_name, color, action in [
            ("minus", _COLORS.text_muted, "minimize"),
            ("maximize-2", _COLORS.text_muted, "maximize"),
            ("x", "#ef4444", "close"),
        ]:
            btn = QToolButton()
            btn.setFixedSize(QSize(32, 28))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(render_svg_icon(lucide_icon_path(icon_name), 16, color))
            btn.setIconSize(QSize(16, 16))
            if action == "close":
                set_button_role(btn, "windowClose")
            else:
                set_button_role(btn, "windowControl")
            if action == "minimize":
                btn.clicked.connect(lambda: self.window().showMinimized())
            elif action == "maximize":
                btn.clicked.connect(self._on_maximize_clicked)
            else:
                btn.clicked.connect(lambda: self.window().close())
            controls_row.addWidget(btn)

        outer.addLayout(controls_row)
        outer.addStretch(1)

        self._center_row = center_row = QHBoxLayout()
        center_row.addStretch(1)

        self._column = column = QWidget()
        column.setFixedWidth(_FORM_WIDTH)
        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(_SPACING.gap_md)

        # Heading
        self._title = title = QLabel("Welcome back")
        set_label_role(title, "loginFormTitle")
        col.addWidget(title)

        self._heading_subtitle = QLabel("Sign in to continue to your studio")
        set_label_role(self._heading_subtitle, "loginSubtitle")
        col.addWidget(self._heading_subtitle)
        # Stored so onboarding mode can collapse the gap below the heading.
        self._sp_after_subtitle = QSpacerItem(0, _SPACING.gap_lg, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        col.addItem(self._sp_after_subtitle)

        # Segmented tab control
        self._tab_container = self._build_tab_bar()
        col.addWidget(self._tab_container)
        self._sp_after_tabs = QSpacerItem(0, _SPACING.gap_md, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        col.addItem(self._sp_after_tabs)

        # Stacked forms
        self._form_stack = QStackedWidget()
        self._form_stack.addWidget(self._build_login_form())
        self._form_stack.addWidget(self._build_register_form())
        self._form_stack.setCurrentIndex(0)
        col.addWidget(self._form_stack)

        # Message areas
        self._message_area = self._build_message_area()
        col.addWidget(self._message_area)

        center_row.addWidget(column)
        center_row.addStretch(1)
        outer.addLayout(center_row)
        outer.addStretch(1)
        return panel

    def _build_tab_bar(self) -> QWidget:
        tab_container = QWidget()
        set_panel_role(tab_container, "loginTabBar")
        tab_row = QHBoxLayout(tab_container)
        tab_row.setSpacing(4)
        tab_row.setContentsMargins(4, 4, 4, 4)

        self._login_tab_btn = QPushButton("  Login")
        self._register_tab_btn = QPushButton("  Register")
        self._login_tab_btn.setProperty("iconName", "log-in")
        self._register_tab_btn.setProperty("iconName", "user-plus")
        for btn in (self._login_tab_btn, self._register_tab_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setMinimumHeight(_TAB_HEIGHT)
            btn.setIconSize(QSize(18, 18))
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )

        self._login_tab_btn.setChecked(True)
        self._apply_tab_style(self._login_tab_btn, active=True)
        self._apply_tab_style(self._register_tab_btn, active=False)
        tab_row.addWidget(self._login_tab_btn)
        tab_row.addWidget(self._register_tab_btn)
        return tab_container

    def _build_message_area(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        set_label_role(self._error_label, "loginError")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        self._success_label = QLabel("")
        self._success_label.setWordWrap(True)
        set_label_role(self._success_label, "loginSuccess")
        self._success_label.setVisible(False)
        layout.addWidget(self._success_label)

        self._field_errors_label = QLabel("")
        self._field_errors_label.setWordWrap(True)
        set_label_role(self._field_errors_label, "loginFieldErrors")
        self._field_errors_label.setVisible(False)
        layout.addWidget(self._field_errors_label)

        self._retry_button = QPushButton("Retry Connection")
        set_button_role(self._retry_button, "secondary")
        self._retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_button.setVisible(False)
        layout.addWidget(self._retry_button)
        return wrap

    # ------------------------------------------------------------------
    # Forms
    # ------------------------------------------------------------------

    def _build_login_form(self) -> QWidget:
        form = QWidget()
        layout = QVBoxLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_GAP_FIELD)

        self._login_email = self._create_field("Email", "Enter your email")
        layout.addWidget(self._login_email["container"])

        self._login_password = self._create_field(
            "Password", "Enter your password", is_password=True
        )
        layout.addWidget(self._login_password["container"])

        # Forgot password link (right-aligned)
        forgot_row = QHBoxLayout()
        forgot_row.setContentsMargins(0, 0, 0, 0)
        forgot_row.addStretch(1)
        self._forgot_btn = text_link("Forgot password?")
        forgot_row.addWidget(self._forgot_btn)
        layout.addLayout(forgot_row)

        layout.addSpacing(_SPACING.gap_sm)
        self._login_submit_btn = self._build_submit_button("Sign In", "log-in")
        layout.addWidget(self._login_submit_btn)
        return form

    def _build_register_form(self) -> QWidget:
        form = QWidget()
        layout = QVBoxLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_GAP_FIELD)

        self._register_email = self._create_field("Email", "Enter your email")
        layout.addWidget(self._register_email["container"])

        self._register_password = self._create_field(
            "Password", "Choose a password", is_password=True
        )
        layout.addWidget(self._register_password["container"])

        self._register_display_name = self._create_field(
            "Display Name", "Choose a display name"
        )
        layout.addWidget(self._register_display_name["container"])

        layout.addSpacing(_SPACING.gap_sm)
        self._register_submit_btn = self._build_submit_button(
            "Create Account", "user-plus"
        )
        layout.addWidget(self._register_submit_btn)
        return form

    def _build_submit_button(self, text: str, icon_name: str) -> QPushButton:
        btn = button_primary(text, icon_text="")
        btn.setIcon(render_svg_icon(lucide_icon_path(icon_name), 18, "#ffffff"))
        btn.setIconSize(QSize(18, 18))
        return btn

    def _create_field(
        self, label_text: str, placeholder: str, *, is_password: bool = False
    ) -> dict:
        """Create a labeled input field. Password fields get a show/hide toggle."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_GAP_LABEL)

        label = QLabel(label_text)
        set_label_role(label, "loginFieldLabel")
        layout.addWidget(label)

        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(_INPUT_HEIGHT)
        set_field_role(input_field, "loginInput")

        # Higher-contrast placeholder
        pal = input_field.palette()
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(_COLORS.text_muted))
        input_field.setPalette(pal)

        toggle_action = None
        if is_password:
            input_field.setEchoMode(QLineEdit.EchoMode.Password)
            eye_icon = render_svg_icon(
                lucide_icon_path("eye"), 18, _COLORS.text_muted
            )
            toggle_action = input_field.addAction(
                eye_icon, QLineEdit.ActionPosition.TrailingPosition
            )

            def _toggle() -> None:
                if input_field.echoMode() == QLineEdit.EchoMode.Password:
                    input_field.setEchoMode(QLineEdit.EchoMode.Normal)
                    toggle_action.setIcon(
                        render_svg_icon(
                            lucide_icon_path("eye-off"), 18, _COLORS.text_secondary
                        )
                    )
                else:
                    input_field.setEchoMode(QLineEdit.EchoMode.Password)
                    toggle_action.setIcon(
                        render_svg_icon(
                            lucide_icon_path("eye"), 18, _COLORS.text_muted
                        )
                    )

            toggle_action.triggered.connect(_toggle)

        layout.addWidget(input_field)
        return {
            "container": container,
            "label": label,
            "input": input_field,
            "toggle": toggle_action,
        }

    # ------------------------------------------------------------------
    # Styling helpers (property role toggling only)
    # ------------------------------------------------------------------

    def _apply_tab_style(self, button: QPushButton, *, active: bool) -> None:
        """Toggle tab between loginTabActive/loginTabInactive roles and tint icon."""
        if active:
            set_button_role(button, "loginTabActive")
        else:
            set_button_role(button, "loginTabInactive")

        # Tint the tab icon to match the active/inactive state
        icon_name = button.property("iconName")
        if icon_name:
            color = "#ffffff" if active else _COLORS.text_muted
            button.setIcon(render_svg_icon(lucide_icon_path(icon_name), 16, color))

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._login_tab_btn.clicked.connect(self._on_login_tab_clicked)
        self._register_tab_btn.clicked.connect(self._on_register_tab_clicked)
        self._login_submit_btn.clicked.connect(self._on_login_submit)
        self._register_submit_btn.clicked.connect(self._on_register_submit)
        self._retry_button.clicked.connect(self._on_retry_clicked)
        self._forgot_btn.clicked.connect(self.forgot_password_requested.emit)

        # Enter key submits the active form
        self._login_email["input"].returnPressed.connect(self._on_login_submit)
        self._login_password["input"].returnPressed.connect(self._on_login_submit)
        self._register_email["input"].returnPressed.connect(self._on_register_submit)
        self._register_password["input"].returnPressed.connect(self._on_register_submit)
        self._register_display_name["input"].returnPressed.connect(
            self._on_register_submit
        )

    # ------------------------------------------------------------------
    # Focus
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        """Autofocus the active form's first field and enable DWM rounded corners."""
        super().showEvent(event)
        if self._form_stack.currentIndex() == 0:
            self._login_email["input"].setFocus()
        else:
            self._register_email["input"].setFocus()

        # Enable Windows DWM rounded corners on frameless window
        self._enable_dwm_rounded_corners()

    def _enable_dwm_rounded_corners(self) -> None:
        """Use Windows DWM API to apply rounded corners to this frameless window."""
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes  # noqa: F401

            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2

            hwnd = int(self.winId())
            preference = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(preference),
                ctypes.sizeof(preference),
            )
        except Exception:
            pass  # Fails gracefully on Windows 10 or older

    # --- Window dragging (title-bar zone only) ---
    #
    # Only the top strip of the window acts as a drag / double-click-maximize
    # handle. Without this, clicking ANYWHERE in the content area would move or
    # maximize the window — and maximizing a fixed-size frameless window makes
    # it resize/jump unexpectedly.
    _DRAG_ZONE_HEIGHT = 48

    def _in_drag_zone(self, event) -> bool:
        try:
            return event.position().y() <= self._DRAG_ZONE_HEIGHT
        except Exception:
            return False

    def _on_maximize_clicked(self) -> None:
        from python_app.app.window_config import toggle_maximize
        toggle_maximize(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._in_drag_zone(event):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            self._drag_pos = None
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if getattr(self, "_drag_pos", None) is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self.isMaximized():
                # Restore to pre-maximize size, keeping cursor relative to window width
                from PyQt6.QtCore import QRect
                prev = self.property("_pre_maximize_geo")
                if isinstance(prev, QRect) and prev.isValid():
                    ratio = event.position().x() / max(self.width(), 1)
                    new_x = int(event.globalPosition().x() - ratio * prev.width())
                    new_y = int(event.globalPosition().y() - event.position().y())
                    self.setGeometry(new_x, new_y, prev.width(), prev.height())
                    self.setProperty("_pre_maximize_geo", None)
                else:
                    self.showNormal()
                # Recalculate drag offset after resize
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if not self._in_drag_zone(event):
            super().mouseDoubleClickEvent(event)
            return
        from python_app.app.window_config import toggle_maximize
        toggle_maximize(self)

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_login_tab_clicked(self) -> None:
        self._form_stack.setCurrentIndex(0)
        self._apply_tab_style(self._login_tab_btn, active=True)
        self._apply_tab_style(self._register_tab_btn, active=False)
        self._heading_subtitle.setText("Sign in to continue to your studio")
        self._clear_messages()
        self._login_email["input"].setFocus()
        self.switch_to_login.emit()

    def _on_register_tab_clicked(self) -> None:
        self._form_stack.setCurrentIndex(1)
        self._apply_tab_style(self._login_tab_btn, active=False)
        self._apply_tab_style(self._register_tab_btn, active=True)
        self._heading_subtitle.setText("Create an account to get started")
        self._clear_messages()
        self._register_email["input"].setFocus()
        self.switch_to_register.emit()

    def _on_login_submit(self) -> None:
        if self._is_loading:
            return
        email = self._login_email["input"].text().strip()
        password = self._login_password["input"].text()
        if not email or not password:
            self.show_error("Please enter both email and password.")
            return
        self._clear_messages()
        self.login_requested.emit(email, password)

    def _on_register_submit(self) -> None:
        if self._is_loading:
            return
        email = self._register_email["input"].text().strip()
        password = self._register_password["input"].text()
        display_name = self._register_display_name["input"].text().strip()
        if not email or not password or not display_name:
            self.show_error("Please fill in all fields.")
            return

        errors: dict[str, str] = {}
        if "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Please enter a valid email address."
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."
        elif len(password) > 128:
            errors["password"] = "Password must be at most 128 characters."
        else:
            if not any(c.isupper() for c in password):
                errors["password"] = "Password must contain an uppercase letter."
            elif not any(c.islower() for c in password):
                errors["password"] = "Password must contain a lowercase letter."
            elif not any(c.isdigit() for c in password):
                errors["password"] = "Password must contain a digit."
        if len(display_name) < 2:
            errors["display_name"] = "Display name must be at least 2 characters."
        elif len(display_name) > 50:
            errors["display_name"] = "Display name must be at most 50 characters."

        if errors:
            self.show_field_errors(errors)
            return

        self._clear_messages()
        self.register_requested.emit(email, password, display_name)

    def _on_retry_clicked(self) -> None:
        self._retry_button.setVisible(False)
        if self._form_stack.currentIndex() == 0:
            self._on_login_submit()
        else:
            self._on_register_submit()

    def _clear_messages(self) -> None:
        self._error_label.setVisible(False)
        self._error_label.setText("")
        self._success_label.setVisible(False)
        self._success_label.setText("")
        self._field_errors_label.setVisible(False)
        self._field_errors_label.setText("")
        self._retry_button.setVisible(False)

    # ------------------------------------------------------------------
    # Public slots
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(bool(message))
        self._success_label.setVisible(False)
        self._field_errors_label.setVisible(False)
        lower_msg = message.lower()
        is_network_error = any(
            keyword in lower_msg
            for keyword in ("connection", "network", "unreachable", "timeout", "retry")
        )
        self._retry_button.setVisible(is_network_error)

    @pyqtSlot(dict)
    def show_field_errors(self, errors: dict) -> None:
        if not errors:
            self._field_errors_label.setVisible(False)
            return
        lines = [f"• {field}: {msg}" for field, msg in errors.items()]
        self._field_errors_label.setText("\n".join(lines))
        self._field_errors_label.setVisible(True)
        self._error_label.setVisible(False)
        self._success_label.setVisible(False)

    @pyqtSlot(str)
    def show_success(self, message: str) -> None:
        self._success_label.setText(message)
        self._success_label.setVisible(bool(message))
        self._error_label.setVisible(False)
        self._field_errors_label.setVisible(False)
        self._retry_button.setVisible(False)

    @pyqtSlot(bool)
    def set_loading(self, is_loading: bool) -> None:
        self._is_loading = is_loading

        self._login_email["input"].setEnabled(not is_loading)
        self._login_password["input"].setEnabled(not is_loading)
        self._login_submit_btn.setEnabled(not is_loading)
        self._login_submit_btn.setText("  Signing in..." if is_loading else "  Sign In")

        self._register_email["input"].setEnabled(not is_loading)
        self._register_password["input"].setEnabled(not is_loading)
        self._register_display_name["input"].setEnabled(not is_loading)
        self._register_submit_btn.setEnabled(not is_loading)
        self._register_submit_btn.setText(
            "  Creating account..." if is_loading else "  Create Account"
        )

        self._login_tab_btn.setEnabled(not is_loading)
        self._register_tab_btn.setEnabled(not is_loading)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def login_email_input(self) -> QLineEdit:
        return self._login_email["input"]

    @property
    def login_password_input(self) -> QLineEdit:
        return self._login_password["input"]

    @property
    def register_email_input(self) -> QLineEdit:
        return self._register_email["input"]

    @property
    def register_password_input(self) -> QLineEdit:
        return self._register_password["input"]

    @property
    def register_display_name_input(self) -> QLineEdit:
        return self._register_display_name["input"]

    @property
    def login_button(self) -> QPushButton:
        return self._login_submit_btn

    @property
    def register_button(self) -> QPushButton:
        return self._register_submit_btn

    @property
    def retry_btn(self) -> QPushButton:
        return self._retry_button

    @property
    def error_label(self) -> QLabel:
        return self._error_label

    @property
    def success_label(self) -> QLabel:
        return self._success_label

    @property
    def field_errors_label(self) -> QLabel:
        return self._field_errors_label

    @property
    def is_login_mode(self) -> bool:
        return self._form_stack.currentIndex() == 0

    @property
    def is_register_mode(self) -> bool:
        return self._form_stack.currentIndex() == 1
