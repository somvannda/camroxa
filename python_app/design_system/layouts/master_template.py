"""Master template for consistent UI controls across the application.

Provides factory methods for creating buttons, inputs, labels, headings,
text, and links with consistent styling that inherits from the design system.
All controls use the purple gradient theme and adapt to their parent layout.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from python_app.design_system.tokens import DEFAULT_DARK_THEME

# ── Typography tokens ──────────────────────────────────────
_font_family = DEFAULT_DARK_THEME.typography.font_family
_size_title = DEFAULT_DARK_THEME.typography.size_title
_size_subtitle = DEFAULT_DARK_THEME.typography.size_subtitle
_size_body = DEFAULT_DARK_THEME.typography.size_body
_size_caption = DEFAULT_DARK_THEME.typography.size_caption
_weight_regular = DEFAULT_DARK_THEME.typography.weight_regular
_weight_medium = DEFAULT_DARK_THEME.typography.weight_medium
_weight_bold = DEFAULT_DARK_THEME.typography.weight_bold

# ── Color tokens ───────────────────────────────────────────
_text_primary = DEFAULT_DARK_THEME.colors.text_primary
_text_secondary = DEFAULT_DARK_THEME.colors.text_secondary
_text_muted = DEFAULT_DARK_THEME.colors.text_muted
_accent = DEFAULT_DARK_THEME.colors.secondary_accent  # #7466F1 purple
_accent_hover = DEFAULT_DARK_THEME.colors.secondary_accent_hover  # #A259FF
_surface_overlay = DEFAULT_DARK_THEME.colors.surface_overlay
_border = DEFAULT_DARK_THEME.colors.border
_danger = DEFAULT_DARK_THEME.colors.danger


# ── Headings ───────────────────────────────────────────────

def heading_h1(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Large heading — 24px bold. Use for page titles."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, 24, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {_text_primary}; background: transparent; border: none;")
    return label


def heading_h2(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Section heading — 20px bold. Use for card/section titles."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, 20, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {_text_primary}; background: transparent; border: none;")
    return label


def heading_h3(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Sub-section heading — 16px bold. Use for sub-sections."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, 16, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {_text_primary}; background: transparent; border: none;")
    return label


# ── Text ───────────────────────────────────────────────────

def text_body(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Body text — 14px regular. Use for descriptions, paragraphs."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, _size_body))
    label.setStyleSheet(f"color: {_text_primary}; background: transparent; border: none;")
    return label


def text_secondary(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Secondary text — 14px regular, muted color. Use for subtitles, secondary info."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, _size_body))
    label.setStyleSheet(f"color: {_text_secondary}; background: transparent; border: none;")
    return label


def text_muted(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Muted text — 12px regular. Use for captions, timestamps."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, _size_caption))
    label.setStyleSheet(f"color: {_text_muted}; background: transparent; border: none;")
    return label


def text_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Form field label — 13px medium. Use above inputs."""
    label = QLabel(text, parent)
    label.setFont(QFont(_font_family, 13, QFont.Weight.Medium))
    label.setStyleSheet(f"color: {_text_secondary}; background: transparent; border: none;")
    return label


# ── Links ──────────────────────────────────────────────────

def text_link(text: str = "", parent: QWidget | None = None) -> QPushButton:
    """Hyperlink-styled text — purple, underlined on hover. Use for navigation links."""
    btn = QPushButton(text, parent)
    btn.setFont(QFont(_font_family, _size_body))
    btn.setStyleSheet(f"""
        QPushButton {{
            color: {_accent};
            background: transparent;
            border: none;
        }}
        QPushButton:hover {{
            color: {_accent_hover};
            text-decoration: underline;
        }}
    """)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFlat(True)
    return btn


# ── Inputs ─────────────────────────────────────────────────

def input_field(
    placeholder: str = "",
    *,
    password: bool = False,
    parent: QWidget | None = None,
) -> QLineEdit:
    """Standard text input — 48px height, purple border on focus.
    Use for all form fields."""
    field = QLineEdit(parent)
    field.setPlaceholderText(placeholder)
    field.setFixedHeight(48)
    field.setFont(QFont(_font_family, _size_body))
    field.setEchoMode(
        QLineEdit.EchoMode.Password if password else QLineEdit.EchoMode.Normal
    )
    field.setStyleSheet(f"""
        QLineEdit {{
            background: {_surface_overlay};
            border: 1px solid {_border};
            border-radius: 8px;
            color: {_text_primary};
            padding: 0 16px;
            font-size: {_size_body}px;
        }}
        QLineEdit:focus {{
            border-color: {_accent};
        }}
        QLineEdit:disabled {{
            background: #0a0e1a;
            color: {_text_muted};
        }}
    """)
    return field


# ── Buttons ────────────────────────────────────────────────

def button_primary(
    text: str = "",
    *,
    icon_text: str = "",
    parent: QWidget | None = None,
) -> QPushButton:
    """Primary CTA button — purple gradient, expands to fill width.
    Use for main actions (submit, confirm, etc.)."""
    display = f"{icon_text} {text}".strip() if icon_text else text
    btn = QPushButton(display, parent)
    btn.setFixedHeight(48)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setProperty("uiRole", "gradientPrimary")
    return btn


def button_secondary(
    text: str = "",
    *,
    icon_text: str = "",
    parent: QWidget | None = None,
) -> QPushButton:
    """Secondary button — transparent with border.
    Use for cancel, back, secondary actions."""
    display = f"{icon_text} {text}".strip() if icon_text else text
    btn = QPushButton(display, parent)
    btn.setFixedHeight(44)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {_text_secondary};
            border: 1px solid {_border};
            border-radius: 8px;
            font-size: {_size_body}px;
            font-weight: {_weight_medium};
        }}
        QPushButton:hover {{
            background: rgba(116, 102, 241, 0.1);
            border-color: {_accent};
            color: {_text_primary};
        }}
        QPushButton:disabled {{
            color: {_text_muted};
            border-color: {_surface_overlay};
        }}
    """)
    return btn


def button_ghost(
    text: str = "",
    *,
    icon_text: str = "",
    parent: QWidget | None = None,
) -> QPushButton:
    """Ghost button — no border, text only. Use for inline actions."""
    display = f"{icon_text} {text}".strip() if icon_text else text
    btn = QPushButton(display, parent)
    btn.setFixedHeight(36)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {_accent};
            border: none;
            border-radius: 6px;
            font-size: {_size_body}px;
            font-weight: {_weight_medium};
        }}
        QPushButton:hover {{
            background: rgba(116, 102, 241, 0.1);
            color: {_accent_hover};
        }}
        QPushButton:disabled {{
            color: {_text_muted};
        }}
    """)
    return btn


def button_danger(
    text: str = "",
    *,
    icon_text: str = "",
    parent: QWidget | None = None,
) -> QPushButton:
    """Danger button — red. Use for destructive actions."""
    display = f"{icon_text} {text}".strip() if icon_text else text
    btn = QPushButton(display, parent)
    btn.setFixedHeight(44)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {_danger};
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-size: {_size_body}px;
            font-weight: {_weight_bold};
        }}
        QPushButton:hover {{
            background: #ff8f82;
        }}
        QPushButton:disabled {{
            background: {_surface_overlay};
            color: {_text_muted};
        }}
    """)
    return btn


# ── Composite form group ───────────────────────────────────

def form_group(
    label_text: str,
    *,
    placeholder: str = "",
    password: bool = False,
    parent: QWidget | None = None,
) -> tuple[QLabel, QLineEdit]:
    """Create a label + input pair. Returns (label, input) for layout."""
    label = text_label(label_text, parent)
    field = input_field(placeholder, password=password, parent=parent)
    return label, field


# ── Layout helpers ─────────────────────────────────────────

def form_column(parent: QWidget | None = None) -> QVBoxLayout:
    """Create a vertical layout with consistent spacing for forms."""
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(20)
    return layout
