
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton,
    QFileDialog, QLineEdit, QComboBox, QProgressBar, QColorDialog,
    QScrollArea, QCheckBox, QMessageBox, QTabWidget, QListWidget,
    QListWidgetItem, QStackedWidget, QToolButton, QTextEdit, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor

from .helpers.style_helper import render_svg_icon, set_panel_role, set_button_role
from .helpers import widget_factory

class CoreViewMixin:
    def _build_primary_placeholder_page(self, title: str, subtitle: str) -> QWidget:
        page = QWidget()
        set_panel_role(page, 'center')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)
        layout.addStretch(1)
        card, body = widget_factory.make_panel_section(title, self.ui, subtitle_text=subtitle, soft=False)
        title_lab = QLabel('Planned Page')
        self._set_label_role(title_lab, 'metricTitle')
        body.addWidget(title_lab)
        desc_lab = QLabel('This area is intentionally blank for the next development phase.')
        self._set_label_role(desc_lab, 'statusMuted')
        desc_lab.setWordWrap(True)
        body.addWidget(desc_lab)
        layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)
        return page

    def _build_app_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(58)
        set_panel_role(header, 'appHeader')
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)
        brand_logo_label = QLabel()
        brand_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_logo_label.setPixmap(QIcon(self._project_icon_path('electric-guitar.svg')).pixmap(QSize(22, 22)))
        layout.addWidget(brand_logo_label)
        brand_copy = QVBoxLayout()
        brand_copy.setContentsMargins(0, 0, 0, 0)
        brand_copy.setSpacing(0)
        brand_title = QLabel('Music Generator')
        self._set_label_role(brand_title, 'sectionTitle')
        brand_copy.addWidget(brand_title)
        brand_subtitle = QLabel('Desktop Studio')
        self._set_label_role(brand_subtitle, 'statusMuted')
        brand_copy.addWidget(brand_subtitle)
        layout.addLayout(brand_copy)
        layout.addStretch(1)
        profile_icon = QLabel()
        profile_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _cache = getattr(self, "_svg_icon_cache", None)
        if _cache is None:
            _cache = {}
            self._svg_icon_cache = _cache
        profile_icon.setPixmap(render_svg_icon(self._lucide_icon_path('user-round'), 18, self.ui['text_soft'], cache=_cache).pixmap(QSize(18, 18)))
        layout.addWidget(profile_icon)
        profile_copy = QVBoxLayout()
        profile_copy.setContentsMargins(0, 0, 0, 0)
        profile_copy.setSpacing(0)
        profile_name = QLabel(self._resolve_display_user_name())
        self._set_label_role(profile_name, 'headerUserName')
        profile_copy.addWidget(profile_name)
        self.header_suno_credits_label = QLabel('Credits: —')
        self._set_label_role(self.header_suno_credits_label, 'statusMuted')
        profile_copy.addWidget(self.header_suno_credits_label)
        layout.addLayout(profile_copy)
        header_logout = QToolButton()
        header_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        header_logout.setToolTip('Logout')
        header_logout.setFixedSize(30, 30)
        self._set_widget_property(header_logout, 'uiRole', 'headerLogout')
        self._set_lucide_icon(header_logout, 'log-out', 16)
        header_logout.clicked.connect(self._show_logout_placeholder)
        layout.addWidget(header_logout)
        return header

    def _build_global_footer(self) -> QWidget:
        footer = QWidget()
        set_panel_role(footer, 'footer')
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 6, 12, 6)
        footer_layout.setSpacing(10)
        self.footer_left_label = QLabel('Ready')
        self._set_label_role(self.footer_left_label, 'statusMuted')
        footer_layout.addWidget(self.footer_left_label)
        footer_layout.addStretch(1)
        self.footer_center_label = QLabel('Template: New Template')
        self._set_label_role(self.footer_center_label, 'statusMuted')
        footer_layout.addWidget(self.footer_center_label)
        footer_layout.addStretch(1)
        self.footer_right_label = QLabel('Output: Not selected')
        self._set_label_role(self.footer_right_label, 'statusMuted')
        footer_layout.addWidget(self.footer_right_label)
        return footer

    def _build_primary_navigation_shell(self) -> QWidget:
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QPixmap, QPainter
        from PyQt6.QtSvg import QSvgRenderer
        from .helpers.style_helper import render_svg_icon
        from python_app.app.resources import icon_path

        nav = QWidget()
        nav.setFixedWidth(260)
        set_panel_role(nav, 'sidebar')
        outer_layout = QVBoxLayout(nav)
        outer_layout.setContentsMargins(16, 16, 16, 12)
        outer_layout.setSpacing(4)

        # --- User profile section (centered at top) ---
        profile_section = QWidget()
        profile_section.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        profile_vbox = QVBoxLayout(profile_section)
        profile_vbox.setContentsMargins(0, 8, 0, 16)
        profile_vbox.setSpacing(8)
        profile_vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Circular profile picture (centered)
        avatar_size = 72
        user_avatar_label = QLabel()
        user_avatar_label.setFixedSize(QSize(avatar_size, avatar_size))
        user_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        user_avatar_label.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #7466F1, stop:1 #A259FF);"
            f"border-radius: {avatar_size // 2}px;"
            "color: #ffffff;"
            "font-size: 26px;"
            "font-weight: 700;"
        )
        user_name_text = self._resolve_display_user_name()
        initials = "".join(w[0].upper() for w in user_name_text.split()[:2]) if user_name_text else "U"
        user_avatar_label.setText(initials)
        profile_vbox.addWidget(user_avatar_label, 0, Qt.AlignmentFlag.AlignHCenter)

        user_name_label = QLabel(user_name_text)
        self._set_label_role(user_name_label, "sidebarUserName")
        _nf = user_name_label.font()
        _nf.setBold(True)
        user_name_label.setFont(_nf)
        profile_vbox.addWidget(user_name_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Plan badge (centered, below name)
        self._sidebar_plan_badge = QLabel("")
        self._sidebar_plan_badge.setStyleSheet(
            "background-color: #F2C94C;"
            "color: #1a1a2e;"
            "font-size: 10px;"
            "font-weight: 700;"
            "padding: 2px 8px;"
            "border-radius: 4px;"
        )
        self._sidebar_plan_badge.hide()
        profile_vbox.addWidget(self._sidebar_plan_badge, 0, Qt.AlignmentFlag.AlignHCenter)

        # Credit balance + expiry (centered, single line)
        self._sidebar_credit_label = QLabel("")
        self._set_label_role(self._sidebar_credit_label, "sidebarPlanLabel")
        self._sidebar_credit_label.setStyleSheet(
            "color: rgba(255,255,255,0.5); font-size: 11px; background: transparent;"
        )
        profile_vbox.addWidget(self._sidebar_credit_label, 0, Qt.AlignmentFlag.AlignHCenter)

        outer_layout.addWidget(profile_section)

        # --- Separator ---
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.06);")
        outer_layout.addWidget(sep)
        outer_layout.addSpacing(8)

        # --- Menu items ---
        menu_items = [
            ('home', 'Dashboard', 'house'),
            ('workflow', 'Workflow', 'workflow'),
            ('progress', 'Progress', 'activity'),
            ('music', 'Music', 'music'),
            ('image', 'Image', 'image'),
            ('video', 'Video', 'video'),
            ('merger', 'Merger', 'git-merge'),
            ('settings', 'Settings', 'settings'),
            ('log', 'Log', 'scroll-text'),
        ]

        self._primary_nav_buttons: dict[str, QPushButton] = {}
        self._primary_page_index: dict[str, int] = {}
        _icon_cache: dict = {}

        nav_container = QWidget()
        nav_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 0, 8, 0)
        nav_layout.setSpacing(2)

        for key, label_text, icon_name in menu_items:
            btn = QPushButton()
            btn.setText(f"  {label_text}")
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("navKey", key)
            btn.setProperty("lucideName", icon_name)

            icon_qicon = render_svg_icon(
                self._lucide_icon_path(icon_name), 20, self.ui['text_muted'], cache=_icon_cache
            )
            btn.setIcon(icon_qicon)
            btn.setIconSize(QSize(20, 20))

            set_button_role(btn, "navItem")
            btn._icon_cache = _icon_cache

            def _make_click_handler(k: str):
                def handler():
                    self._set_primary_page(k)
                return handler

            btn.clicked.connect(_make_click_handler(key))

            nav_layout.addWidget(btn)
            self._primary_nav_buttons[key] = btn

        outer_layout.addWidget(nav_container)
        outer_layout.addStretch(1)

        # --- Bottom separator + logout ---
        bottom_sep = QWidget()
        bottom_sep.setFixedHeight(1)
        bottom_sep.setStyleSheet("background-color: rgba(255, 255, 255, 0.06);")
        outer_layout.addWidget(bottom_sep)
        outer_layout.addSpacing(4)

        logout_btn = QPushButton("  Logout")
        logout_btn.setFixedHeight(44)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setToolTip("Logout")
        set_button_role(logout_btn, "sidebarLogout")
        logout_icon = render_svg_icon(
            self._lucide_icon_path("log-out"), 20, "#ef4444", cache=_icon_cache
        )
        logout_btn.setIcon(logout_icon)
        logout_btn.setIconSize(QSize(20, 20))
        logout_btn.clicked.connect(self._show_logout_placeholder)
        outer_layout.addWidget(logout_btn)

        return nav

    def update_sidebar_license(self, plan_name: str | None, expires_at: str | None, credit_balance: int | None = None) -> None:
        """Update sidebar plan badge, credit balance, and expiry date."""
        # Plan badge
        badge = getattr(self, "_sidebar_plan_badge", None)
        if badge is not None:
            if plan_name:
                display = plan_name.capitalize()
                badge.setText(display)
                badge.show()
            else:
                badge.hide()

        # Credit balance + expiry on one line
        credit_label = getattr(self, "_sidebar_credit_label", None)
        if credit_label is not None:
            credit_text = f"Credits: {credit_balance:,}" if credit_balance is not None else "Credits: —"
            if expires_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    expiry_text = f"Expires: {dt.strftime('%b %d, %Y')}"
                except Exception:
                    expiry_text = f"Expires: {expires_at[:10]}"
            elif plan_name == "lifetime":
                expiry_text = "Expires: Never"
            else:
                expiry_text = ""
            if expiry_text:
                credit_label.setText(f"{credit_text} | {expiry_text}")
            else:
                credit_label.setText(credit_text)
