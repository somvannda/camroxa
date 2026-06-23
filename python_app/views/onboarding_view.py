"""Onboarding views: email confirmation + channel setup wizard.

Multi-page flow with left-to-right slide transitions:
1. Confirm Code — 6-digit input, auto-submit, resend timer
2. Channel Wizard — genre → names (primary+secondary) → logos (both) → covers (both) → description → done
"""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QSize, QTimer, pyqtSignal,
)
from PyQt6.QtGui import QFont, QColor, QPixmap, QImage
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QStackedWidget, QComboBox, QFrame, QScrollArea, QGridLayout,
    QSizePolicy, QSpacerItem, QProgressBar, QTextEdit, QSplitter,
)
import base64

from python_app.design_system.layouts.master_template import (
    heading_h1, heading_h2, heading_h3,
    text_body, text_secondary, text_muted, text_label, text_link,
    input_field, button_primary, button_secondary, button_ghost,
)

try:
    import os, tempfile
    from python_app.views.helpers.style_helper import render_svg_icon
    from python_app.app.resources import lucide_icon_path
    _svg_path = lucide_icon_path("chevron-down")
    if os.path.exists(_svg_path):
        _arrow_icon = render_svg_icon(_svg_path, 16, "#8a8fa8")
        _arrow_png = os.path.join(tempfile.gettempdir(), "camxora_combo_arrow.png")
        _arrow_icon.pixmap(16, 16).save(_arrow_png, "PNG")
except Exception:
    pass


# ────────────────────────────────────────────────────────────
# Slide transition helper
# ────────────────────────────────────────────────────────────

class SlideStackedWidget(QStackedWidget):
    """QStackedWidget with left-to-right slide animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation_duration = 350
        self._direction = "right"

    def slide_to(self, index: int, direction: str = "right") -> None:
        if index == self.currentIndex():
            return
        if index < 0 or index >= self.count():
            return

        self._direction = direction
        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        width = self.width()
        offset_start = QPoint(width, 0) if direction == "right" else QPoint(-width, 0)
        offset_end = QPoint(-width, 0) if direction == "right" else QPoint(width, 0)

        next_widget.setGeometry(0, 0, width, self.height())
        next_widget.move(offset_start)
        next_widget.show()
        next_widget.raise_()

        anim = QPropertyAnimation(next_widget, b"pos")
        anim.setDuration(self._animation_duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(offset_start)
        anim.setEndValue(QPoint(0, 0))
        anim.start()

        if not hasattr(self, "_anims"):
            self._anims = []
        self._anims.append(anim)
        anim.finished.connect(lambda: self._cleanup_anim(anim))

        self.setCurrentIndex(index)

    def _cleanup_anim(self, anim):
        if anim in self._anims:
            self._anims.remove(anim)


# ────────────────────────────────────────────────────────────
# Page 1: Email Confirmation Code
# ────────────────────────────────────────────────────────────

class ConfirmCodePage(QWidget):
    """6-digit email verification code input page."""

    verified = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._email = ""
        self._resend_seconds = 0
        self._setup_ui()

    def set_email(self, email: str) -> None:
        self._email = email
        self._email_label.setText(f"We sent a code to {email}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Outer wrapper centers the card
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card frame
        card = QWidget()
        card.setFixedWidth(420)
        card.setStyleSheet("""
            QWidget {
                background: #0c1230;
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 16px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 40, 32, 32)
        card_layout.setSpacing(20)

        title = heading_h1("Verify your email")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        self._email_label = text_secondary("We sent a code to your email")
        self._email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._email_label)

        self._code_input = QLineEdit()
        self._code_input.setFixedHeight(56)
        self._code_input.setMaxLength(6)
        self._code_input.setFont(QFont("Open Sans", 28, QFont.Weight.Bold))
        self._code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code_input.setPlaceholderText("------")
        self._code_input.setStyleSheet("""
            QLineEdit {
                background: #111738;
                border: 2px solid rgba(116,102,241,0.3);
                border-radius: 12px;
                color: #ffffff;
                letter-spacing: 12px;
                padding: 0 16px;
            }
            QLineEdit:focus {
                border-color: #7466F1;
            }
        """)
        self._resend_callback = None  # Set by controller
        self._code_input.textChanged.connect(self._on_code_changed)
        card_layout.addWidget(self._code_input)

        self._error_label = text_muted("")
        self._error_label.setStyleSheet("color: #FF7262; background: transparent; border: none;")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.hide()
        card_layout.addWidget(self._error_label)

        self._verify_btn = QPushButton("Verify")
        self._verify_btn.setFixedHeight(44)
        self._verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._verify_btn.setEnabled(False)
        self._verify_btn.setProperty("uiRole", "gradientPrimary")
        self._verify_btn.clicked.connect(self._on_verify)
        card_layout.addWidget(self._verify_btn)

        resend_row = QHBoxLayout()
        resend_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._resend_label = text_muted("Didn't receive a code?")
        resend_row.addWidget(self._resend_label)

        self._resend_btn = button_ghost("Resend")
        self._resend_btn.clicked.connect(self._on_resend)
        resend_row.addWidget(self._resend_btn)
        card_layout.addLayout(resend_row)

        wrapper_layout.addStretch(1)
        wrapper_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        wrapper_layout.addStretch(1)

        layout.addWidget(wrapper)

    def _on_code_changed(self, text: str):
        self._verify_btn.setEnabled(len(text) == 6)
        self._error_label.hide()

    def _on_verify(self):
        code = self._code_input.text().strip()
        if len(code) != 6:
            return
        self._verify_btn.setEnabled(False)
        self._verify_btn.setText("Verifying...")
        self.verified.emit()

    def _on_resend(self):
        if self._resend_seconds > 0:
            return
        self._resend_seconds = 60
        self._resend_btn.setEnabled(False)
        self._resend_btn.setText(f"Resend ({self._resend_seconds}s)")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_resend)
        self._timer.start(1000)
        if self._resend_callback:
            self._resend_callback()

    def _tick_resend(self):
        self._resend_seconds -= 1
        if self._resend_seconds <= 0:
            self._timer.stop()
            self._resend_btn.setEnabled(True)
            self._resend_btn.setText("Resend")
        else:
            self._resend_btn.setText(f"Resend ({self._resend_seconds}s)")

    def show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.show()
        self._verify_btn.setEnabled(True)
        self._verify_btn.setText("Verify")

    def reset(self):
        self._code_input.clear()
        self._error_label.hide()
        self._verify_btn.setEnabled(False)
        self._verify_btn.setText("Verify")


# ────────────────────────────────────────────────────────────
# Logo spinner overlay (purple arc spinning around circle)
# ────────────────────────────────────────────────────────────

class _LogoSpinner(QWidget):
    """A transparent overlay that draws a spinning purple arc around a circle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

    def start(self):
        self._timer.start(20)  # ~50fps smooth
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 3) % 360
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen
        from PyQt6.QtCore import QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(4, 4, self.width() - 8, self.height() - 8)

        # Purple arc pen
        pen = QPen(QColor(116, 102, 241, 200))  # #7466F1
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        # Draw a 90-degree arc that rotates clockwise
        start_angle = -self._angle * 16  # Qt uses 1/16th degree units
        span_angle = 90 * 16  # 90 degree arc
        painter.drawArc(rect, start_angle, span_angle)

        painter.end()


# ────────────────────────────────────────────────────────────
# Page 2: Channel Setup Wizard (Primary + Secondary)
# ────────────────────────────────────────────────────────────

class ChannelWizardPage(QWidget):
    """Multi-step channel setup wizard — creates both Primary and Secondary channels at once."""

    completed = pyqtSignal()
    step_changed = pyqtSignal(int)  # emits 0-based step index

    _STEP_TITLES = [
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
        "Setting Up Your Channel Profiles",
    ]

    _NAME_BTN_NORMAL = "QPushButton { background: #111738; border: 1px solid rgba(116,102,241,0.2); border-radius: 8px; color: #eef4ff; font-size: 14px; font-weight: 600; padding: 0 16px; text-align: left; } QPushButton:hover { border-color: #7466F1; background: rgba(116,102,241,0.1); }"
    _NAME_BTN_SELECTED = "QPushButton { background: #7466F1; border: 1px solid #7466F1; border-radius: 8px; color: #fff; font-size: 14px; font-weight: 600; padding: 0 16px; text-align: left; }"
    _PRIMARY_ACCENT = "#0ACF83"
    _SECONDARY_ACCENT = "#1ABCFE"
    _NEXT_BTN_STYLE = """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7466F1, stop:1 #A259FF);
            color: #ffffff;
            min-height: 48px;
            border-radius: 8px;
            border: none;
            font-weight: bold;
            padding: 0 16px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b6fff, stop:1 #b87dff);
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5a3dc7, stop:1 #7c4dff);
        }
        QPushButton:disabled {
            background: #1a1f3d;
            color: #5a5f7d;
            border: none;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._genre = ""
        self._genre_match_key = ""
        self._genre_match_keys: dict[str, str] = {}
        self._primary_name = ""
        self._secondary_name = ""
        self._primary_logo_b64 = ""
        self._secondary_logo_b64 = ""
        self._primary_covers_b64s: list[str] = []
        self._secondary_covers_b64s: list[str] = []
        self._description = ""
        self._keywords: list[str] = []
        self._tags: list[str] = []
        self._shared_generate_count = 0
        self._primary_logo_history: list[str] = []
        self._secondary_logo_history: list[str] = []
        self._primary_refresh_count = 0
        self._secondary_refresh_count = 0
        self._genres: list[dict] = []
        self._pending_custom_prompt = ''
        self._setup_ui()

    _STEP_DEFS = [
        ("🎵", "Pick Your Genre", "Choose your music genre"),
        ("✏️", "Choose Names", "Pick unique channel names"),
        ("🎨", "Design Logos", "Create visual identity"),
        ("🖼️", "Cover Art", "YouTube banners"),
        ("📝", "Description", "SEO content & tags"),
    ]

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content_wrapper = QWidget()
        content_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_wrapper.setStyleSheet("background: transparent;")
        wrapper_layout = QVBoxLayout(content_wrapper)
        # Tight top margin (and small bottom margin) so the step content has the
        # maximum vertical room and doesn't need to scroll.
        wrapper_layout.setContentsMargins(20, 12, 20, 24)
        wrapper_layout.setSpacing(0)

        self._step_header = QWidget()
        self._step_header.setStyleSheet("background: transparent;")
        sh_layout = QVBoxLayout(self._step_header)
        sh_layout.setContentsMargins(10, 0, 0, 0)
        sh_layout.setSpacing(0)

        self._step_emoji = QLabel("🎵")
        self._step_emoji.setFont(QFont("Open Sans", 32))
        self._step_emoji.setStyleSheet("background: transparent; color: #ffffff;")
        # Crop the emoji's tall line box so the title sits closer beneath it (issue 1)
        self._step_emoji.setFixedHeight(40)
        sh_layout.addWidget(self._step_emoji)

        # Tight gap between the emoji and the title (issue 1)
        sh_layout.addSpacing(2)

        self._step_title = heading_h1("Setting Up Your Channel Profiles")
        sh_layout.addWidget(self._step_title)

        # 10px padding below the title (issue 2)
        sh_layout.addSpacing(10)

        self._step_subtitle = text_secondary("Step 1 of 5 — Choose your music genre")
        self._step_subtitle.setWordWrap(True)
        sh_layout.addWidget(self._step_subtitle)

        # Extra 10px below the "Step x of 5" line so the progress row has more breathing room (issue 3)
        sh_layout.addSpacing(26)

        wrapper_layout.addWidget(self._step_header)

        progress_container = QWidget()
        progress_container.setStyleSheet("background: transparent;")
        pc_layout = QHBoxLayout(progress_container)
        # Match the progress row width to the step content / Next button
        # (content uses left=10, right=30 margins) so it starts at "Music Genre"
        # and ends at the Next button's right edge (issue 4)
        pc_layout.setContentsMargins(10, 0, 30, 0)
        pc_layout.setSpacing(0)

        self._step_dots = []
        self._step_labels = []
        self._step_lines = []
        for i, (emoji, label, _) in enumerate(self._STEP_DEFS):
            dot_col = QWidget()
            dot_col.setStyleSheet("background: transparent;")
            dot_col_layout = QVBoxLayout(dot_col)
            dot_col_layout.setContentsMargins(0, 0, 0, 0)
            dot_col_layout.setSpacing(8)

            dot = QPushButton(str(i + 1))
            dot.setFixedSize(36, 36)
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.setFont(QFont("Open Sans", 12, QFont.Weight.Bold))
            dot.setStyleSheet("""
                QPushButton {
                    background: #1a1f3d;
                    color: #5a5f7d;
                    border-radius: 18px;
                    border: 2px solid #2a2f4d;
                    min-width: 36px;
                    max-width: 36px;
                    min-height: 36px;
                    max-height: 36px;
                    padding: 0px;
                }
            """)
            dot.clicked.connect(lambda checked, idx=i: self._on_dot_clicked(idx))
            dot_col_layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignHCenter)

            lbl = QLabel(label)
            lbl.setFont(QFont("Open Sans", 10))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #8a8fa8; background: transparent; border: none;")
            dot_col_layout.addWidget(lbl, 0, Qt.AlignmentFlag.AlignHCenter)

            self._step_dots.append(dot)
            self._step_labels.append(lbl)
            pc_layout.addWidget(dot_col, 1)

            if i < len(self._STEP_DEFS) - 1:
                line_spacer = QWidget()
                line_spacer.setStyleSheet("background: transparent;")
                ls_layout = QVBoxLayout(line_spacer)
                ls_layout.setContentsMargins(0, 17, 0, 0)
                ls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                line = QWidget()
                line.setFixedHeight(2)
                line.setMinimumWidth(40)
                line.setStyleSheet("background: #2a2f4d;")
                self._step_lines.append(line)
                ls_layout.addWidget(line)
                pc_layout.addWidget(line_spacer, 2)

        wrapper_layout.addWidget(progress_container)

        wrapper_layout.addSpacing(16)

        self._current_step = 0
        self._stack = SlideStackedWidget()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._stack.addWidget(self._build_genre_step())
        self._stack.addWidget(self._build_name_step())
        self._stack.addWidget(self._build_logo_step())
        self._stack.addWidget(self._build_covers_step())
        self._stack.addWidget(self._build_description_step())

        wrapper_layout.addWidget(self._stack, 1)

        layout.addWidget(content_wrapper)

        self._update_progress(0)

    def _update_progress(self, step: int):
        self._current_step = step
        _circle = "min-width:36px; max-width:36px; min-height:36px; max-height:36px; padding:0px;"
        for i, (dot, lbl) in enumerate(zip(self._step_dots, self._step_labels)):
            if i < step:
                dot.setStyleSheet(f"""
                    QPushButton {{
                        background: #7466F1;
                        color: #ffffff;
                        border-radius: 18px;
                        border: 2px solid #7466F1;
                        {_circle}
                    }}
                    QPushButton:hover {{ background: #5a4fe1; }}
                """)
                dot.setEnabled(True)
                dot.setCursor(Qt.CursorShape.PointingHandCursor)
                lbl.setStyleSheet("color: #7466F1; background: transparent; border: none; font-weight: bold;")
            elif i == step:
                dot.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7466F1, stop:1 #A259FF);
                        color: #ffffff;
                        border-radius: 18px;
                        border: 2px solid #A259FF;
                        {_circle}
                    }}
                """)
                dot.setEnabled(False)
                dot.setCursor(Qt.CursorShape.ArrowCursor)
                lbl.setStyleSheet("color: #ffffff; background: transparent; border: none; font-weight: bold;")
            else:
                dot.setStyleSheet(f"""
                    QPushButton {{
                        background: #1a1f3d;
                        color: #5a5f7d;
                        border-radius: 18px;
                        border: 2px solid #2a2f4d;
                        {_circle}
                    }}
                """)
                dot.setEnabled(False)
                dot.setCursor(Qt.CursorShape.ArrowCursor)
                lbl.setStyleSheet("color: #8a8fa8; background: transparent; border: none;")

        for i, line in enumerate(self._step_lines):
            if i < step:
                line.setStyleSheet("background: #7466F1;")
            else:
                line.setStyleSheet("background: #2a2f4d;")

        if step < len(self._STEP_DEFS):
            emoji, title, subtitle = self._STEP_DEFS[step]
            self._step_emoji.setText(emoji)
            self._step_title.setText(title)
            self._step_subtitle.setText(f"Step {step + 1} of 5 — {subtitle}")

    def _on_dot_clicked(self, idx: int):
        if idx < self._current_step:
            self._go_to_step(idx)

    # ── Step builders ──────────────────────────────────────

    def _build_scroll_wrapper(self, inner_fn):
        # Wrap each wizard step in a real scroll area so tall content fits inside
        # the fixed 720px-high window (instead of forcing the window taller).
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        inner_fn(inner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #1a1f3d; width: 8px; border-radius: 4px; }"
            "QScrollBar::handle:vertical { background: #3a3f5d; border-radius: 4px; min-height: 30px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        scroll.setWidget(inner)
        return scroll

    def _add_nav_buttons(self, v, step_index: int, next_text: str = "Next →", next_callback=None, next_attr: str = None):
        """Add full-width next button to step layout."""
        next_btn = button_primary(next_text)
        next_btn.setStyleSheet(self._NEXT_BTN_STYLE)
        if next_callback:
            next_btn.clicked.connect(next_callback)
        if next_attr:
            setattr(self, next_attr, next_btn)
        v.addWidget(next_btn)
        v.addStretch()

    def _build_genre_step(self) -> QWidget:
        def build(content):
            v = QVBoxLayout(content)
            v.setContentsMargins(10, 20, 30, 20)
            v.setSpacing(12)

            v.addWidget(heading_h2("Music Genre"))

            subtitle = text_secondary("Select a music genre to generate channel names.")
            subtitle.setWordWrap(True)
            v.addWidget(subtitle)

            v.addSpacing(8)

            v.addWidget(text_label("Genre"))
            self._genre_combo = QComboBox()
            self._genre_combo.setFixedHeight(52)
            self._genre_combo.setFont(QFont("Open Sans", 14))

            import os, tempfile
            _combo_arrow = os.path.join(tempfile.gettempdir(), 'camxora_combo_arrow.png').replace(chr(92), '/')

            self._genre_combo.setStyleSheet(f"""
                QComboBox {{
                    background: #111738;
                    border: 1px solid rgba(116,102,241,0.3);
                    border-radius: 10px;
                    color: #ffffff;
                    padding: 0 40px 0 16px;
                }}
                QComboBox:focus {{ border-color: #7466F1; }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                    border: none;
                    width: 40px;
                }}
                QComboBox::down-arrow {{
                    image: url({_combo_arrow});
                    width: 16px;
                    height: 16px;
                }}
                QComboBox QAbstractItemView {{
                    background: #111738; border: 1px solid rgba(116,102,241,0.3);
                    color: #ffffff; selection-background-color: #7466F1;
                    padding: 4px; outline: none;
                }}
                QComboBox QAbstractItemView::item {{ padding: 8px 16px; min-height: 32px; }}
            """)
            self._genre_combo.currentTextChanged.connect(self._on_genre_changed)
            v.addWidget(self._genre_combo)

            coming_soon = text_muted("More genres coming soon — we're expanding our library regularly.")
            coming_soon.setWordWrap(True)
            v.addWidget(coming_soon)

            v.addSpacing(16)

            promo_card = QWidget()
            promo_card.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0c1230, stop:1 #111738);
                border: 1px solid rgba(116,102,241,0.15);
                border-radius: 12px;
            """)
            promo_layout = QVBoxLayout(promo_card)
            promo_layout.setContentsMargins(20, 20, 20, 20)
            promo_layout.setSpacing(16)

            promo_title = QLabel("Why Complete Your Channel Profiles?")
            promo_title.setFont(QFont("Open Sans", 14, QFont.Weight.Bold))
            promo_title.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            promo_layout.addWidget(promo_title)

            promo_bullets = [
                "Get AI-generated channel names, logos, banners, and SEO descriptions tailored to your genre.",
                "Your profiles unlock full access to batch song generation, spectrum video rendering, and one-click YouTube publishing.",
                "Use the materials we create for you to launch a professional, monetization-ready YouTube channel.",
                "Every asset is designed to work together — consistent branding across your entire channel from day one.",
            ]
            for bullet in promo_bullets:
                row = QWidget()
                row.setStyleSheet("background: transparent; border: none;")
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(12)
                dot = QLabel("✦")
                dot.setFont(QFont("Open Sans", 10))
                dot.setStyleSheet("color: #7466F1; background: transparent; border: none;")
                dot.setFixedWidth(16)
                row_layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
                txt = QLabel(bullet)
                txt.setFont(QFont("Open Sans", 12))
                txt.setWordWrap(True)
                txt.setStyleSheet("color: #b0b5c8; background: transparent; border: none;")
                row_layout.addWidget(txt, 1)
                promo_layout.addWidget(row)

            v.addWidget(promo_card)

            self._add_nav_buttons(v, 0, "Next →", lambda: self._go_to_step(1), "_genre_next_btn")
        return self._build_scroll_wrapper(build)

    def _build_channel_column(self, label: str, accent_color: str) -> dict:
        """Build a single channel column widget with header, status, manual input, scrollable name list, and refresh."""
        card = QWidget()
        card.setStyleSheet("background: #0c1230; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)

        header = heading_h3(label)
        header.setStyleSheet(f"color: {accent_color}; background: transparent; border: none;")
        card_layout.addWidget(header)

        status = text_muted("Generating...")
        card_layout.addWidget(status)

        manual_input = input_field("Type your own name...")
        card_layout.addWidget(manual_input)

        # Scroll area for name list (fixed height, aligned top)
        name_scroll = QScrollArea()
        name_scroll.setWidgetResizable(True)
        name_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        name_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        name_scroll.setFixedHeight(220)
        name_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #1a1f3d; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #3a3f5d; border-radius: 3px; min-height: 30px; }
        """)
        name_content = QWidget()
        name_content.setStyleSheet("background: transparent;")
        name_list = QVBoxLayout(name_content)
        name_list.setContentsMargins(0, 0, 4, 0)
        name_list.setSpacing(6)
        name_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        name_scroll.setWidget(name_content)
        card_layout.addWidget(name_scroll, 1)

        refresh_btn = button_ghost("↻ Generate More")
        card_layout.addWidget(refresh_btn)

        return {"card": card, "status": status, "name_list": name_list, "manual_input": manual_input, "refresh_btn": refresh_btn, "name_scroll": name_scroll}

    def _build_name_step(self) -> QWidget:
        def build(content):
            v = QVBoxLayout(content)
            v.setContentsMargins(10, 32, 30, 32)
            v.setSpacing(20)

            credits_card = QWidget()
            credits_card.setStyleSheet("background: #0c1230; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px;")
            credits_layout = QHBoxLayout(credits_card)
            credits_layout.setContentsMargins(16, 10, 16, 10)
            credits_layout.setSpacing(12)

            credits_icon = QLabel("⚡")
            credits_icon.setFont(QFont("Open Sans", 14))
            credits_icon.setStyleSheet("background: transparent; border: none;")
            credits_layout.addWidget(credits_icon)

            credits_text = QVBoxLayout()
            credits_text.setSpacing(2)
            self._shared_generate_label = QLabel("3 generates remaining")
            self._shared_generate_label.setFont(QFont("Open Sans", 12, QFont.Weight.Bold))
            self._shared_generate_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            credits_text.addWidget(self._shared_generate_label)

            self._credits_bar = QProgressBar()
            self._credits_bar.setFixedHeight(6)
            self._credits_bar.setRange(0, 3)
            self._credits_bar.setValue(3)
            self._credits_bar.setTextVisible(False)
            self._credits_bar.setStyleSheet("""
                QProgressBar { background: #1a1f3d; border: none; border-radius: 3px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7466F1, stop:1 #A259FF); border-radius: 3px; }
            """)
            credits_text.addWidget(self._credits_bar)

            credits_layout.addLayout(credits_text, 1)
            v.addWidget(credits_card)

            columns_row = QHBoxLayout()
            columns_row.setSpacing(16)

            self._primary_name_col = self._build_channel_column("Primary Channel", self._PRIMARY_ACCENT)
            self._primary_name_col["refresh_btn"].clicked.connect(lambda: self._on_refresh_names("primary"))
            columns_row.addWidget(self._primary_name_col["card"], 1)

            self._secondary_name_col = self._build_channel_column("Secondary Channel", self._SECONDARY_ACCENT)
            self._secondary_name_col["refresh_btn"].clicked.connect(lambda: self._on_refresh_names("secondary"))
            columns_row.addWidget(self._secondary_name_col["card"], 1)

            v.addLayout(columns_row, 1)

            v.addSpacing(8)

            prompt_container = QWidget()
            prompt_container.setStyleSheet("background: #0c1230; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;")
            prompt_layout = QVBoxLayout(prompt_container)
            prompt_layout.setContentsMargins(16, 12, 16, 12)
            prompt_layout.setSpacing(8)

            prompt_label = text_muted("Not happy with the names? Enter a custom prompt and press Enter to generate more.")
            prompt_label.setWordWrap(True)
            prompt_layout.addWidget(prompt_label)

            self._custom_prompt_input = QLineEdit()
            self._custom_prompt_input.setPlaceholderText("e.g., Dark cyberpunk electronic, moody vibes...")
            self._custom_prompt_input.returnPressed.connect(self._on_custom_prompt_submit)
            self._custom_prompt_input.setStyleSheet("""
                QLineEdit {
                    background: #111738;
                    border: 1px solid rgba(116,102,241,0.3);
                    border-radius: 8px;
                    color: #ffffff;
                    padding: 12px 16px;
                    font-size: 14px;
                }
                QLineEdit:focus { border-color: #7466F1; }
            """)
            prompt_layout.addWidget(self._custom_prompt_input)

            v.addWidget(prompt_container)

            self._add_nav_buttons(v, 1, "Next →", lambda: self._go_to_step(2), "_name_next_btn")
        return self._build_scroll_wrapper(build)

    def _build_logo_column(self, label: str, accent_color: str) -> dict:
        """Build a single logo column with preview, history, and regenerate."""
        card = QWidget()
        card.setStyleSheet("background: #0c1230; border: 1px solid rgba(255,255,255,0.06); border-radius: 12px;")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(10)

        header = heading_h3(label)
        header.setStyleSheet(f"color: {accent_color}; background: transparent; border: none;")
        card_layout.addWidget(header)

        # Logo preview container (holds both the preview label and the spinner overlay)
        preview_container = QWidget()
        preview_container.setFixedSize(210, 210)
        preview_container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(preview_container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        preview = QLabel("Generating...")
        preview.setFixedSize(200, 200)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: #111738; border-radius: 100px; color: rgba(255,255,255,0.3); font-size: 12px;")
        container_layout.addWidget(preview)

        # Spinning border animation overlay
        spinner = _LogoSpinner(preview_container)
        spinner.setFixedSize(210, 210)
        spinner.move(0, 0)
        spinner.raise_()
        spinner.start()

        card_layout.addWidget(preview_container, 0, Qt.AlignmentFlag.AlignCenter)

        count_label = text_muted("Refreshes remaining: 3")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(count_label)

        history_row = QHBoxLayout()
        history_row.setSpacing(6)
        history_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addLayout(history_row)

        # Buttons row: Regenerate + Upload
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        refresh_btn = button_ghost("↻ Regenerate")
        btn_row.addWidget(refresh_btn)

        upload_btn = button_ghost("📁 Upload")
        btn_row.addWidget(upload_btn)

        card_layout.addLayout(btn_row)

        return {"card": card, "preview": preview, "count_label": count_label, "history_row": history_row, "refresh_btn": refresh_btn, "upload_btn": upload_btn, "spinner": spinner}

    def _build_logo_step(self) -> QWidget:
        def build(content):
            v = QVBoxLayout(content)
            v.setContentsMargins(10, 32, 30, 32)
            v.setSpacing(20)

            v.addWidget(heading_h2("Design your logos"))

            subtitle = text_secondary("We'll generate a logo for each channel. You can regenerate up to 3 times each.")
            v.addWidget(subtitle)

            timing_note = text_muted("Logo generation typically takes 20–60 seconds. Please be patient while our AI creates your unique design.")
            timing_note.setWordWrap(True)
            v.addWidget(timing_note)

            columns_row = QHBoxLayout()
            columns_row.setSpacing(16)

            self._primary_logo_col = self._build_logo_column("Primary Logo", self._PRIMARY_ACCENT)
            self._primary_logo_col["refresh_btn"].clicked.connect(lambda: self._on_refresh_logo("primary"))
            self._primary_logo_col["upload_btn"].clicked.connect(lambda: self._on_upload_logo("primary"))
            columns_row.addWidget(self._primary_logo_col["card"], 1)

            self._secondary_logo_col = self._build_logo_column("Secondary Logo", self._SECONDARY_ACCENT)
            self._secondary_logo_col["refresh_btn"].clicked.connect(lambda: self._on_refresh_logo("secondary"))
            self._secondary_logo_col["upload_btn"].clicked.connect(lambda: self._on_upload_logo("secondary"))
            columns_row.addWidget(self._secondary_logo_col["card"], 1)

            v.addLayout(columns_row)

            self._add_nav_buttons(v, 2, "Next →", lambda: self._go_to_step(3), "_logo_next_btn")
        return self._build_scroll_wrapper(build)

    def _build_covers_step(self) -> QWidget:
        def build(content):
            v = QVBoxLayout(content)
            v.setContentsMargins(10, 32, 30, 32)
            v.setSpacing(20)

            v.addWidget(heading_h2("Channel cover images"))

            subtitle = text_secondary("YouTube banners for each channel. Click any to download.")
            v.addWidget(subtitle)

            timing_note = text_muted("Cover generation typically takes 20–60 seconds per image. Please be patient while our AI designs your banners.")
            timing_note.setWordWrap(True)
            v.addWidget(timing_note)

            # Primary covers
            p_header = text_label("Primary Channel")
            p_header.setStyleSheet(f"color: {self._PRIMARY_ACCENT}; background: transparent; border: none;")
            v.addWidget(p_header)

            self._primary_covers_grid = QGridLayout()
            self._primary_covers_grid.setSpacing(10)
            v.addLayout(self._primary_covers_grid)

            self._primary_covers_status = text_muted("Generating covers...")
            self._primary_covers_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(self._primary_covers_status)

            p_btn_row = QHBoxLayout()
            p_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            p_btn_row.setSpacing(12)

            p_refresh = button_ghost("↻ Regenerate Primary")
            p_refresh.clicked.connect(lambda: self._on_refresh_covers("primary"))
            self._primary_covers_refresh_btn = p_refresh
            p_btn_row.addWidget(p_refresh)

            p_upload = button_ghost("📁 Upload Cover")
            p_upload.clicked.connect(lambda: self._on_upload_cover("primary"))
            p_btn_row.addWidget(p_upload)

            v.addLayout(p_btn_row)

            v.addSpacing(16)

            # Secondary covers
            s_header = text_label("Secondary Channel")
            s_header.setStyleSheet(f"color: {self._SECONDARY_ACCENT}; background: transparent; border: none;")
            v.addWidget(s_header)

            self._secondary_covers_grid = QGridLayout()
            self._secondary_covers_grid.setSpacing(10)
            v.addLayout(self._secondary_covers_grid)

            self._secondary_covers_status = text_muted("Generating covers...")
            self._secondary_covers_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(self._secondary_covers_status)

            s_btn_row = QHBoxLayout()
            s_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s_btn_row.setSpacing(12)

            s_refresh = button_ghost("↻ Regenerate Secondary")
            s_refresh.clicked.connect(lambda: self._on_refresh_covers("secondary"))
            self._secondary_covers_refresh_btn = s_refresh
            s_btn_row.addWidget(s_refresh)

            s_upload = button_ghost("📁 Upload Cover")
            s_upload.clicked.connect(lambda: self._on_upload_cover("secondary"))
            s_btn_row.addWidget(s_upload)

            v.addLayout(s_btn_row)

            self._add_nav_buttons(v, 3, "Next →", lambda: self._go_to_step(4))
        return self._build_scroll_wrapper(build)

    def _build_description_step(self) -> QWidget:
        def build(content):
            v = QVBoxLayout(content)
            v.setContentsMargins(10, 32, 30, 32)
            v.setSpacing(20)

            summary_card = QWidget()
            summary_card.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0c1230, stop:1 #111738);
                border: 1px solid rgba(116,102,241,0.15);
                border-radius: 12px;
            """)
            summary_layout = QVBoxLayout(summary_card)
            summary_layout.setContentsMargins(24, 20, 24, 20)
            summary_layout.setSpacing(16)

            summary_header = QLabel("Your Channel Profiles")
            summary_header.setFont(QFont("Open Sans", 16, QFont.Weight.Bold))
            summary_header.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            summary_layout.addWidget(summary_header)

            # Store reference for dynamic refresh
            self._desc_summary_card = summary_card

            v.addWidget(summary_card)

            v.addWidget(heading_h2("Channel Description & SEO"))

            subtitle = text_secondary("Copy-paste these into your YouTube channel settings.")
            v.addWidget(subtitle)

            # Description label + refresh
            desc_header = QHBoxLayout()
            desc_header.addWidget(text_label("Channel Description"))
            desc_header.addStretch()
            desc_refresh = button_ghost("⟳")
            desc_refresh.setFixedWidth(36)
            desc_refresh.setToolTip("Regenerate description")
            desc_refresh.clicked.connect(self._load_description)
            desc_header.addWidget(desc_refresh)
            v.addLayout(desc_header)

            self._desc_text = QTextEdit()
            self._desc_text.setFixedHeight(120)
            self._desc_text.setReadOnly(False)
            self._desc_text.setFont(QFont("Open Sans", 12))
            self._desc_text.setStyleSheet("""
                QTextEdit { background: #111738; border: 1px solid rgba(116,102,241,0.2); border-radius: 8px; color: #eef4ff; padding: 12px; }
            """)
            v.addWidget(self._desc_text)

            copy_desc_btn = button_ghost("Copy Description")
            copy_desc_btn.clicked.connect(lambda: self._copy_text(self._desc_text.toPlainText()))
            v.addWidget(copy_desc_btn)

            v.addSpacing(8)

            # Keywords label + refresh
            kw_header = QHBoxLayout()
            kw_header.addWidget(text_label("Channel Keywords"))
            kw_header.addStretch()
            kw_refresh = button_ghost("⟳")
            kw_refresh.setFixedWidth(36)
            kw_refresh.setToolTip("Regenerate keywords")
            kw_refresh.clicked.connect(self._load_description)
            kw_header.addWidget(kw_refresh)
            v.addLayout(kw_header)

            self._keywords_text = QTextEdit()
            self._keywords_text.setFixedHeight(60)
            self._keywords_text.setReadOnly(False)
            self._keywords_text.setFont(QFont("Open Sans", 12))
            self._keywords_text.setStyleSheet("""
                QTextEdit { background: #111738; border: 1px solid rgba(116,102,241,0.2); border-radius: 8px; color: #eef4ff; padding: 12px; }
            """)
            v.addWidget(self._keywords_text)

            copy_kw_btn = button_ghost("Copy Keywords")
            copy_kw_btn.clicked.connect(lambda: self._copy_text(self._keywords_text.toPlainText()))
            v.addWidget(copy_kw_btn)

            v.addSpacing(8)

            # Tags label + refresh
            tags_header = QHBoxLayout()
            tags_header.addWidget(text_label("Channel Tags"))
            tags_header.addStretch()
            tags_refresh = button_ghost("⟳")
            tags_refresh.setFixedWidth(36)
            tags_refresh.setToolTip("Regenerate tags")
            tags_refresh.clicked.connect(self._load_description)
            tags_header.addWidget(tags_refresh)
            v.addLayout(tags_header)

            self._tags_text = QTextEdit()
            self._tags_text.setFixedHeight(60)
            self._tags_text.setReadOnly(False)
            self._tags_text.setFont(QFont("Open Sans", 12))
            self._tags_text.setStyleSheet("""
                QTextEdit { background: #111738; border: 1px solid rgba(116,102,241,0.2); border-radius: 8px; color: #eef4ff; padding: 12px; }
            """)
            v.addWidget(self._tags_text)

            copy_tags_btn = button_ghost("Copy Tags")
            copy_tags_btn.clicked.connect(lambda: self._copy_text(self._tags_text.toPlainText()))
            v.addWidget(copy_tags_btn)

            self._add_nav_buttons(v, 4, "Create Both Channel Profiles →", self._on_finish, "_finish_btn")
        return self._build_scroll_wrapper(build)

    # ── Navigation ─────────────────────────────────────────

    def _copy_text(self, text: str):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _on_genre_changed(self, text: str):
        self._genre = text
        # The admin channel prompt is matched by the description's match_key.
        self._genre_match_key = self._genre_match_keys.get(text, text)
        self._genre_next_btn.setEnabled(bool(text))

    def _go_to_step(self, step: int):
        self._stack.slide_to(step, "right")
        self._update_progress(step)
        self.step_changed.emit(step)

        if step == 1:
            # Only generate names if user hasn't selected any yet
            if not self._primary_name and not self._secondary_name:
                self._on_refresh_names("both")
        elif step == 2:
            # Only generate logos if none exist yet
            if not self._primary_logo_b64 and not self._secondary_logo_b64:
                self._on_refresh_logo("both")
        elif step == 3:
            # Only generate covers if none exist yet
            if not self._primary_covers_b64s and not self._secondary_covers_b64s:
                self._on_refresh_covers("both")
        elif step == 4:
            self._load_description()

    # ── Name step ──────────────────────────────────────────

    def _update_shared_generate_label(self):
        remaining = 3 - self._shared_generate_count
        # Restore the bar to determinate mode (the "generating" animation sets it
        # to an indeterminate range while a request is in flight).
        self._credits_bar.setRange(0, 3)
        if remaining <= 0:
            self._shared_generate_label.setText("No generates remaining")
            self._credits_bar.setValue(0)
        else:
            self._shared_generate_label.setText(f"{remaining} generate{'s' if remaining != 1 else ''} remaining")
            self._credits_bar.setValue(remaining)

    def _set_credits_generating(self, is_generating: bool):
        """Toggle the credits bar between an animated 'generating' state and the
        normal remaining-count gauge."""
        if is_generating:
            # Range (0, 0) makes QProgressBar render an animated indeterminate
            # marquee — our 'generating' animation.
            self._shared_generate_label.setText("Generating names…")
            self._credits_bar.setRange(0, 0)
        else:
            self._update_shared_generate_label()

    def _on_refresh_names(self, target: str):
        if self._shared_generate_count >= 3:
            self._shared_generate_label.setText("Max 3 generates reached")
            return

        self._shared_generate_count += 1
        remaining = 3 - self._shared_generate_count
        self._update_shared_generate_label()
        # Kick off the animated generating indicator
        self._set_credits_generating(True)

        if target in ("primary", "both"):
            col = self._primary_name_col
            col["status"].setText("Generating names...")
            col["refresh_btn"].setEnabled(False)
            col["refresh_btn"].setText(f"Generating... ({remaining} left)")
            if "manual_input" in col:
                col["manual_input"].clear()
            if target != "both":
                self._primary_name = ""
        if target in ("secondary", "both"):
            col = self._secondary_name_col
            col["status"].setText("Generating names...")
            col["refresh_btn"].setEnabled(False)
            col["refresh_btn"].setText(f"Generating... ({remaining} left)")
            if "manual_input" in col:
                col["manual_input"].clear()
            if target != "both":
                self._secondary_name = ""

        # Single API call for both channels — the callback generates 20 names
        # and splits them 10/10 between primary and secondary.
        if hasattr(self, '_generate_names_callback'):
            self._generate_names_callback(self._genre, target)

    def set_names(self, names: list[str], role: str = "primary"):
        col = self._primary_name_col if role == "primary" else self._secondary_name_col
        col["status"].setText("Pick a name or type your own:")
        col["status"].setStyleSheet("color: #8a8fa8; background: transparent; border: none;")

        # Stop the generating animation and restore the remaining-count gauge.
        self._set_credits_generating(False)

        remaining = 3 - self._shared_generate_count
        if remaining > 0:
            col["refresh_btn"].setEnabled(True)
            col["refresh_btn"].setText(f"↻ Generate More ({remaining} left)")
        else:
            col["refresh_btn"].setEnabled(False)
            col["refresh_btn"].setText("Max generates reached")

        name_list = col["name_list"]
        while name_list.count():
            item = name_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for name in names:
            btn = QPushButton(name)
            btn.setFixedHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._NAME_BTN_NORMAL)
            btn.clicked.connect(lambda checked, n=name, r=role: self._select_name(n, r))
            name_list.addWidget(btn)

        manual_input = col.get("manual_input")
        if manual_input:
            manual_input.clear()
            manual_input.textChanged.connect(lambda text, r=role: self._on_manual_name_changed(text, r))
            manual_input.returnPressed.connect(lambda r=role: self._on_manual_name_submit(r))

        self._check_names_ready()

    def set_names_error(self, message: str, role: str = "primary"):
        """Surface a name-generation failure in the channel column instead of
        silently showing an empty list. Refunds the consumed generate so the
        user can retry."""
        col = self._primary_name_col if role == "primary" else self._secondary_name_col

        # Refund the generate that was consumed for this failed request.
        self._shared_generate_count = max(0, self._shared_generate_count - 1)
        self._set_credits_generating(False)

        col["status"].setText(message or "Couldn't generate names. Please try again.")
        col["status"].setStyleSheet("color: #FF7262; background: transparent; border: none;")

        remaining = 3 - self._shared_generate_count
        if remaining > 0:
            col["refresh_btn"].setEnabled(True)
            col["refresh_btn"].setText(f"↻ Try Again ({remaining} left)")
        else:
            col["refresh_btn"].setEnabled(False)
            col["refresh_btn"].setText("Max generates reached")

    def _select_name(self, name: str, role: str):
        if role == "primary":
            self._primary_name = name
            col = self._primary_name_col
        else:
            self._secondary_name = name
            col = self._secondary_name_col

        manual_input = col.get("manual_input")
        if manual_input:
            manual_input.blockSignals(True)
            manual_input.clear()
            manual_input.blockSignals(False)

        name_list = col["name_list"]
        for i in range(name_list.count()):
            item = name_list.itemAt(i)
            if item and item.widget():
                btn = item.widget()
                if btn.text() == name:
                    btn.setStyleSheet(self._NAME_BTN_SELECTED)
                else:
                    btn.setStyleSheet(self._NAME_BTN_NORMAL)

        self._update_preview()
        self._check_names_ready()

    def _update_preview(self):
        pass  # Channel preview removed from name step

    def _check_names_ready(self):
        ready = bool(self._primary_name and self._secondary_name)
        self._name_next_btn.setEnabled(ready)

    def _on_manual_name_changed(self, text: str, role: str):
        if role == "primary":
            self._primary_name = text.strip()
            col = self._primary_name_col
        else:
            self._secondary_name = text.strip()
            col = self._secondary_name_col

        name_list = col["name_list"]
        for i in range(name_list.count()):
            item = name_list.itemAt(i)
            if item and item.widget():
                item.widget().setStyleSheet(self._NAME_BTN_NORMAL)

        self._check_names_ready()

    def _on_manual_name_submit(self, role: str):
        col = self._primary_name_col if role == "primary" else self._secondary_name_col
        text = col.get("manual_input", QLineEdit()).text().strip()
        if text:
            self._select_name(text, role)

    def _on_custom_prompt_submit(self):
        prompt = self._custom_prompt_input.text().strip()
        if not prompt:
            return
        remaining = 3 - self._shared_generate_count
        if remaining <= 0:
            return
        self._shared_generate_count += 1
        self._update_shared_generate_label()
        self._set_credits_generating(True)
        self._primary_name_col["refresh_btn"].setEnabled(False)
        self._primary_name_col["refresh_btn"].setText("Generating...")
        self._secondary_name_col["refresh_btn"].setEnabled(False)
        self._secondary_name_col["refresh_btn"].setText("Generating...")
        self._pending_custom_prompt = prompt
        self._custom_prompt_input.clear()
        if hasattr(self, '_generate_names_callback'):
            self._generate_names_callback(self._genre, "both")

    # ── Logo step ──────────────────────────────────────────

    def _on_refresh_logo(self, target: str):
        def _do_one(role: str):
            col = self._primary_logo_col if role == "primary" else self._secondary_logo_col
            count = self._primary_refresh_count if role == "primary" else self._secondary_refresh_count
            if count >= 3:
                return
            if role == "primary":
                self._primary_refresh_count += 1
                remaining = 3 - self._primary_refresh_count
            else:
                self._secondary_refresh_count += 1
                remaining = 3 - self._secondary_refresh_count
            col["count_label"].setText(f"Refreshes remaining: {remaining}")
            col["refresh_btn"].setEnabled(remaining > 0)
            col["preview"].setText("Generating...")
            col["preview"].setPixmap(QPixmap())  # Clear any existing image
            # Start spinner animation
            spinner = col.get("spinner")
            if spinner:
                spinner.start()
            name = self._primary_name if role == "primary" else self._secondary_name
            if hasattr(self, '_generate_logo_callback'):
                self._generate_logo_callback(name, self._genre, role)

        if target in ("primary", "both"):
            _do_one("primary")
        if target in ("secondary", "both"):
            _do_one("secondary")

    def _on_upload_logo(self, role: str):
        """Open file dialog for user to upload their own logo image."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload Logo Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                img_data = f.read()

            # Validate it's a real image
            qimg = QImage.fromData(img_data)
            if qimg.isNull():
                return

            # Convert to base64 and set as logo
            import base64 as _b64
            image_b64 = _b64.b64encode(img_data).decode()
            self.set_logo(image_b64, role)

            # Store for profile creation
            if role == "primary":
                self._primary_logo_b64 = image_b64
            else:
                self._secondary_logo_b64 = image_b64
        except Exception:
            pass

    def set_logo(self, image_b64: str, role: str = "primary"):
        col = self._primary_logo_col if role == "primary" else self._secondary_logo_col
        history = self._primary_logo_history if role == "primary" else self._secondary_logo_history

        # Stop the spinning animation
        spinner = col.get("spinner")
        if spinner:
            spinner.stop()

        if image_b64:
            try:
                img_data = base64.b64decode(image_b64)
                qimg = QImage.fromData(img_data)
                if qimg.isNull():
                    col["preview"].setText("Preview unavailable")
                    return

                # Create circular pixmap for the logo preview
                from PyQt6.QtGui import QPainter, QBrush, QPainterPath
                from PyQt6.QtCore import QRectF

                size = 200
                # Scale source image to fill the circle
                scaled_img = QPixmap.fromImage(qimg).scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                # Crop to square if needed
                if scaled_img.width() != size or scaled_img.height() != size:
                    x = (scaled_img.width() - size) // 2
                    y = (scaled_img.height() - size) // 2
                    scaled_img = scaled_img.copy(x, y, size, size)

                # Create circular mask
                circular = QPixmap(size, size)
                circular.fill(QColor(0, 0, 0, 0))  # Transparent

                painter = QPainter(circular)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                path = QPainterPath()
                path.addEllipse(QRectF(0, 0, size, size))
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, scaled_img)
                painter.end()

                col["preview"].setText("")
                col["preview"].setStyleSheet("background: transparent; border-radius: 100px;")
                col["preview"].setPixmap(circular)
                history.append(image_b64)
                self._update_logo_history(col["history_row"], history)
                # Store for profile creation
                if role == "primary":
                    self._primary_logo_b64 = image_b64
                else:
                    self._secondary_logo_b64 = image_b64
            except Exception as exc:
                import traceback
                traceback.print_exc()
                col["preview"].setText("Preview unavailable")
        else:
            col["preview"].setText("Generation failed — try again")

        # Enable Next button when both logos are ready
        self._check_logos_ready()

    def set_logo_retry(self, role: str = "primary"):
        """Show a 'Retry Preview' button in the logo circle when generation failed."""
        col = self._primary_logo_col if role == "primary" else self._secondary_logo_col

        # Stop spinner
        spinner = col.get("spinner")
        if spinner:
            spinner.stop()

        # Show retry button inside the preview area
        col["preview"].setText("")
        col["preview"].setStyleSheet(
            "background: #111738; border-radius: 100px; border: 1px dashed rgba(116,102,241,0.4);"
        )

        # Create a clickable label that looks like a button inside the circle
        retry_text = "⟳ Retry Preview\n\nYour logo is being generated.\nTap to check if it's ready."
        col["preview"].setText(retry_text)
        col["preview"].setStyleSheet(
            "background: #111738; border-radius: 100px; color: #7466F1; "
            "font-size: 12px; border: 2px dashed rgba(116,102,241,0.4); padding: 20px;"
        )
        col["preview"].setCursor(Qt.CursorShape.PointingHandCursor)

        # Make the preview clickable for retry
        def _on_retry_click(event, r=role):
            col["preview"].setCursor(Qt.CursorShape.ArrowCursor)
            col["preview"].setText("Loading...")
            col["preview"].setStyleSheet(
                "background: #111738; border-radius: 100px; color: rgba(255,255,255,0.3); font-size: 12px;"
            )
            # Restart spinner
            if spinner:
                spinner.start()
            # Retry the API call (no new credits — API handles this)
            name = self._primary_name if r == "primary" else self._secondary_name
            if hasattr(self, '_generate_logo_callback'):
                self._generate_logo_callback(name, self._genre, r)

        col["preview"].mousePressEvent = _on_retry_click

    def _check_logos_ready(self):
        """Enable the logo step Next button only when both logos are set."""
        ready = bool(self._primary_logo_b64 and self._secondary_logo_b64)
        if hasattr(self, '_logo_next_btn'):
            self._logo_next_btn.setEnabled(ready)

    def _update_logo_history(self, history_row, history: list[str]):
        while history_row.count():
            item = history_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for b64 in history:
            try:
                img_data = base64.b64decode(b64)
                qimg = QImage.fromData(img_data)
                thumb = QPixmap.fromImage(qimg).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl = QLabel()
                lbl.setPixmap(thumb)
                lbl.setFixedSize(44, 44)
                lbl.setStyleSheet("border: 2px solid #7466F1; border-radius: 6px;")
                history_row.addWidget(lbl)
            except Exception:
                pass

    # ── Covers step ────────────────────────────────────────

    def _on_refresh_covers(self, target: str):
        if target in ("primary", "both"):
            self._primary_covers_status.setText("Generating covers...")
            self._primary_covers_refresh_btn.setEnabled(False)
            name = self._primary_name
            if hasattr(self, '_generate_covers_callback'):
                self._generate_covers_callback(name, self._genre, "primary")
        if target in ("secondary", "both"):
            self._secondary_covers_status.setText("Generating covers...")
            self._secondary_covers_refresh_btn.setEnabled(False)
            name = self._secondary_name
            if hasattr(self, '_generate_covers_callback'):
                self._generate_covers_callback(name, self._genre, "secondary")

    def set_covers(self, images: list[str], role: str = "primary"):
        if role == "primary":
            self._primary_covers_b64s = images
            self._primary_covers_status.setText("Click any cover to download")
            self._primary_covers_refresh_btn.setEnabled(True)
            grid = self._primary_covers_grid
        else:
            self._secondary_covers_b64s = images
            self._secondary_covers_status.setText("Click any cover to download")
            self._secondary_covers_refresh_btn.setEnabled(True)
            grid = self._secondary_covers_grid

        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, b64 in enumerate(images):
            if not b64:
                continue
            try:
                img_data = base64.b64decode(b64)
                qimg = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(qimg).scaled(260, 65, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

                container = QLabel()
                container.setPixmap(pixmap)
                container.setFixedSize(260, 65)
                container.setStyleSheet("border: 1px solid rgba(116,102,241,0.2); border-radius: 8px;")
                container.setCursor(Qt.CursorShape.PointingHandCursor)
                container.mousePressEvent = lambda _, idx=i, r=role: self._download_cover(idx, r)
                grid.addWidget(container, i // 3, i % 3)
            except Exception:
                pass

    def _download_cover(self, idx: int, role: str):
        from PyQt6.QtWidgets import QFileDialog
        covers = self._primary_covers_b64s if role == "primary" else self._secondary_covers_b64s
        prefix = "primary" if role == "primary" else "secondary"
        if idx < len(covers) and covers[idx]:
            path, _ = QFileDialog.getSaveFileName(self, "Save Cover Image", f"{prefix}-cover-{idx+1}.png", "PNG Files (*.png)")
            if path:
                try:
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(covers[idx]))
                except Exception:
                    pass

    def _on_upload_cover(self, role: str):
        """Open file dialog for user to upload their own cover image."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload Cover Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                img_data = f.read()

            qimg = QImage.fromData(img_data)
            if qimg.isNull():
                return

            import base64 as _b64
            image_b64 = _b64.b64encode(img_data).decode()

            # Add to the covers list for this role
            if role == "primary":
                self._primary_covers_b64s.append(image_b64)
                self.set_covers(self._primary_covers_b64s, "primary")
            else:
                self._secondary_covers_b64s.append(image_b64)
                self.set_covers(self._secondary_covers_b64s, "secondary")
        except Exception:
            pass

    def set_covers_retry(self, role: str = "primary"):
        """Show retry message when cover generation fails."""
        if role == "primary":
            self._primary_covers_status.setText(
                "⟳ Cover generation is taking longer than expected. Tap Regenerate to try again, or upload your own."
            )
            self._primary_covers_status.setStyleSheet("color: #7466F1; background: transparent; border: none;")
            self._primary_covers_refresh_btn.setEnabled(True)
            self._primary_covers_refresh_btn.setText("⟳ Retry Primary")
        else:
            self._secondary_covers_status.setText(
                "⟳ Cover generation is taking longer than expected. Tap Regenerate to try again, or upload your own."
            )
            self._secondary_covers_status.setStyleSheet("color: #7466F1; background: transparent; border: none;")
            self._secondary_covers_refresh_btn.setEnabled(True)
            self._secondary_covers_refresh_btn.setText("⟳ Retry Secondary")

    # ── Description step ───────────────────────────────────

    def _load_description(self):
        # Refresh the summary card with current logo/name data
        self._refresh_description_summary()
        # Trigger AI generation of description, keywords, tags
        if hasattr(self, '_generate_description_callback'):
            self._generate_description_callback(self._primary_name, self._genre)

    def _refresh_description_summary(self):
        """Update the description step summary card with current channel data."""
        if not hasattr(self, '_desc_summary_card'):
            return

        # Clear and rebuild summary content
        layout = self._desc_summary_card.layout()
        if layout is None:
            return

        # Clear existing channel rows (keep header)
        while layout.count() > 1:
            item = layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        channels_data = [
            ("Primary Channel", self._primary_name or "—", self._PRIMARY_ACCENT, self._primary_logo_b64),
            ("Secondary Channel", self._secondary_name or "—", self._SECONDARY_ACCENT, self._secondary_logo_b64),
        ]

        for ch_label, ch_name, ch_color, ch_logo in channels_data:
            ch_row = QWidget()
            ch_row.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 10px;")
            ch_layout = QHBoxLayout(ch_row)
            ch_layout.setContentsMargins(16, 14, 16, 14)
            ch_layout.setSpacing(14)

            logo_preview = QLabel()
            logo_preview.setFixedSize(56, 56)
            logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if ch_logo:
                try:
                    img_data = base64.b64decode(ch_logo)
                    qimg = QImage.fromData(img_data)
                    if not qimg.isNull():
                        from PyQt6.QtGui import QPainter, QPainterPath
                        from PyQt6.QtCore import QRectF
                        scaled = QPixmap.fromImage(qimg).scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        if scaled.width() != 52 or scaled.height() != 52:
                            x = (scaled.width() - 52) // 2
                            y = (scaled.height() - 52) // 2
                            scaled = scaled.copy(x, y, 52, 52)
                        circular = QPixmap(52, 52)
                        circular.fill(QColor(0, 0, 0, 0))
                        painter = QPainter(circular)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        path = QPainterPath()
                        path.addEllipse(QRectF(0, 0, 52, 52))
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, scaled)
                        painter.end()
                        logo_preview.setPixmap(circular)
                        logo_preview.setStyleSheet("background: transparent; border-radius: 28px;")
                    else:
                        logo_preview.setText("🎨")
                        logo_preview.setStyleSheet("background: #1a1f3d; border-radius: 28px; color: rgba(255,255,255,0.3);")
                except Exception:
                    logo_preview.setText("🎨")
                    logo_preview.setStyleSheet("background: #1a1f3d; border-radius: 28px; color: rgba(255,255,255,0.3);")
            else:
                logo_preview.setText("🎨")
                logo_preview.setFont(QFont("Open Sans", 20))
                logo_preview.setStyleSheet("background: #1a1f3d; border-radius: 28px; color: rgba(255,255,255,0.3);")
            ch_layout.addWidget(logo_preview)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)

            ch_label_lbl = QLabel(ch_label)
            ch_label_lbl.setFont(QFont("Open Sans", 11))
            ch_label_lbl.setStyleSheet(f"color: {ch_color}; background: transparent; border: none;")
            info_layout.addWidget(ch_label_lbl)

            ch_name_lbl = QLabel(ch_name)
            ch_name_lbl.setFont(QFont("Open Sans", 15, QFont.Weight.Bold))
            ch_name_lbl.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            info_layout.addWidget(ch_name_lbl)

            ch_genre_lbl = QLabel(self._genre or "—")
            ch_genre_lbl.setFont(QFont("Open Sans", 11))
            ch_genre_lbl.setStyleSheet("color: #8a8fa8; background: transparent; border: none;")
            info_layout.addWidget(ch_genre_lbl)

            ch_layout.addLayout(info_layout, 1)
            layout.addWidget(ch_row)

    def set_description(self, description: str, keywords: list[str], tags: list[str]):
        self._description = description
        self._keywords = keywords
        self._tags = tags
        self._desc_text.setPlainText(description)
        self._keywords_text.setPlainText(", ".join(keywords))
        self._tags_text.setPlainText(", ".join(tags))
        # Hide error/retry if visible
        if hasattr(self, '_desc_error_label'):
            self._desc_error_label.hide()
        if hasattr(self, '_desc_retry_btn'):
            self._desc_retry_btn.hide()

    def set_description_error(self, message: str):
        """Show an error message with a retry button for description generation."""
        self._desc_text.setPlainText("")
        self._keywords_text.setPlainText("")
        self._tags_text.setPlainText("")

        if not hasattr(self, '_desc_error_label'):
            # Create error label + retry button dynamically (first time only)
            self._desc_error_label = QLabel("")
            self._desc_error_label.setStyleSheet("color: #FF7262; background: transparent; border: none; font-size: 13px;")
            self._desc_error_label.setWordWrap(True)
            # Insert into the description step layout
            parent = self._desc_text.parentWidget()
            if parent and parent.layout():
                parent.layout().addWidget(self._desc_error_label)

            self._desc_retry_btn = QPushButton("⟳ Retry Description Generation")
            self._desc_retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._desc_retry_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #7466F1; border: 1px solid #7466F1; "
                "border-radius: 6px; padding: 8px 16px; font-size: 13px; } "
                "QPushButton:hover { background: rgba(116,102,241,0.1); }"
            )
            self._desc_retry_btn.clicked.connect(self._load_description)
            if parent and parent.layout():
                parent.layout().addWidget(self._desc_retry_btn)

        self._desc_error_label.setText(message)
        self._desc_error_label.show()
        self._desc_retry_btn.show()

    # ── Finish ─────────────────────────────────────────────

    def _on_finish(self):
        # Show loading state on the button
        if hasattr(self, '_finish_btn'):
            self._finish_btn.setEnabled(False)
            self._finish_btn.setText("Creating your profiles...")

        if hasattr(self, '_create_profiles_callback'):
            self._create_profiles_callback(
                primary_name=self._primary_name,
                secondary_name=self._secondary_name,
                genre=self._genre,
                primary_logo_b64=self._primary_logo_b64,
                secondary_logo_b64=self._secondary_logo_b64,
                description=self._description,
                keywords=self._keywords,
                tags=self._tags,
            )

    def on_profiles_created(self):
        """Called by controller when both profiles are created successfully."""
        if hasattr(self, '_finish_btn'):
            self._finish_btn.setText("✓ Profiles Created!")
        self.completed.emit()

    def on_profiles_failed(self, message: str = ""):
        """Called by controller when profile creation fails."""
        if hasattr(self, '_finish_btn'):
            self._finish_btn.setEnabled(True)
            self._finish_btn.setText("Create Both Channel Profiles →")

    # ── Public setters ─────────────────────────────────────

    def load_genres(self, genres: list[dict]):
        self._genres = genres
        self._genre_combo.clear()
        self._genre_combo.addItem("-- Select a genre --", "")
        self._genre_match_keys = {"": ""}
        for g in genres:
            name = g.get("name", "")
            # Fall back to the name when a description has no explicit match_key.
            self._genre_match_keys[name] = (g.get("match_key") or name)
            self._genre_combo.addItem(name, g.get("id", ""))

    def reset(self):
        self._stack.slide_to(0, "left")
        self._update_progress(0)
        self._genre = ""
        self._genre_match_key = ""
        self._primary_name = ""
        self._secondary_name = ""
        self._primary_logo_b64 = ""
        self._secondary_logo_b64 = ""
        self._primary_covers_b64s = []
        self._secondary_covers_b64s = []
        self._shared_generate_count = 0
        self._primary_refresh_count = 0
        self._secondary_refresh_count = 0
        self._pending_custom_prompt = ''
        self._primary_logo_history.clear()
        self._secondary_logo_history.clear()
        self._genre_combo.setCurrentIndex(0)
        self._genre_next_btn.setEnabled(False)
        self._name_next_btn.setEnabled(False)
        if hasattr(self, '_logo_next_btn'):
            self._logo_next_btn.setEnabled(False)
        if hasattr(self, '_custom_prompt_input'):
            self._custom_prompt_input.clear()
        if hasattr(self, '_shared_generate_label'):
            self._shared_generate_label.setText("3 generates remaining")
        if hasattr(self, '_credits_bar'):
            self._credits_bar.setValue(3)
        if hasattr(self, '_primary_name_col'):
            self._primary_name_col["manual_input"].clear()
            self._primary_name_col["refresh_btn"].setEnabled(True)
            self._primary_name_col["refresh_btn"].setText("↻ Generate More")
            self._primary_name_col["status"].setText("Generating...")
        if hasattr(self, '_secondary_name_col'):
            self._secondary_name_col["manual_input"].clear()
            self._secondary_name_col["refresh_btn"].setEnabled(True)
            self._secondary_name_col["refresh_btn"].setText("↻ Generate More")
            self._secondary_name_col["status"].setText("Generating...")
