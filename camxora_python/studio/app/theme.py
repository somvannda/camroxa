"""Studio editor theme — rebased onto the camxora_python studio chrome tokens.

The ported standalone editor no longer ships its own independent look: it
consumes the same STUDIO_* tokens that power the Create/Music/Image/Video
studio-chrome pages, and uses the app's Inter font family.
"""

from __future__ import annotations

from dataclasses import dataclass

from features.create.create_styles import (
    STUDIO_BG,
    STUDIO_BORDER,
    STUDIO_BORDER_STRONG,
    STUDIO_INPUT,
    STUDIO_PANEL,
    STUDIO_PURPLE,
    STUDIO_PURPLE_BRIGHT,
    STUDIO_TEXT,
    STUDIO_TEXT_DIM,
    STUDIO_TEXT_MUTED,
    STUDIO_WARNING,
)


@dataclass(frozen=True)
class Palette:
    bg: str = STUDIO_BG
    panel: str = STUDIO_PANEL
    panel2: str = STUDIO_INPUT
    panel3: str = "#16263E"  # raised/hover surface between input and border
    border: str = STUDIO_BORDER
    border_strong: str = STUDIO_BORDER_STRONG
    border_soft: str = "#0F1B2D"
    text: str = STUDIO_TEXT
    text_dim: str = STUDIO_TEXT_MUTED
    text_dimmer: str = STUDIO_TEXT_DIM
    accent: str = STUDIO_PURPLE_BRIGHT
    accent_hi: str = "#8B5CF6"  # hover/checked lighter accent
    # Brand CTA gradient — matches the camxora master theme primary buttons
    # (#7466F1 -> #A259FF, hover #8577F5 -> #B06BFF).
    accent_deep: str = "#7466F1"
    accent_bright: str = "#A259FF"
    accent_deep_hi: str = "#8577F5"
    accent_bright_hi: str = "#B06BFF"
    accent_soft: str = "rgba(99, 53, 217, 0.28)"
    accent2: str = "#EC4899"
    track_video: str = STUDIO_PURPLE_BRIGHT
    track_audio: str = "#00C878"
    track_overlay: str = STUDIO_WARNING
    danger: str = "#FF5470"
    danger_soft: str = "#3A1A22"


PALETTE = Palette()

FONT_DISPLAY = "Inter"
FONT_BODY = "Inter"
FONT_MONO = "Consolas"

# Fallback chain used when the bundled fonts aren't installed/loadable —
# keeps the look close on any OS without requiring network access.
FONT_DISPLAY_FALLBACK = f"{FONT_DISPLAY}, Segoe UI Semibold, Segoe UI, sans-serif"
FONT_BODY_FALLBACK = f"{FONT_BODY}, Segoe UI, Arial, sans-serif"
FONT_MONO_FALLBACK = f"{FONT_MONO}, Consolas, Courier New, monospace"


def build_qss(p: Palette = PALETTE) -> str:
    """Return the global QSS stylesheet applied to the QApplication."""
    return f"""
    * {{
        font-family: "{FONT_BODY}";
        color: {p.text};
        outline: none;
    }}
    QMainWindow, QWidget#AppRoot {{
        background: {p.bg};
    }}
    QWidget {{
        background: transparent;
    }}
    QToolTip {{
        background: {p.panel2};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 4px 8px;
        border-radius: 6px;
    }}

    /* ---------- Topbar ---------- */
    QFrame#Topbar {{
        background: {p.panel};
        border-bottom: 1px solid {p.border};
    }}
    QLabel#LogoLabel {{
        font-family: "{FONT_DISPLAY}";
        font-weight: 800;
        font-size: 16px;
        color: {p.text};
    }}
    QLabel#LogoSubLabel {{
        color: {p.text_dim};
        font-family: "{FONT_MONO}";
        font-size: 11px;
    }}
    QLineEdit#ProjectNameEdit {{
        background: transparent;
        border: 1px solid transparent;
        color: {p.text_dim};
        font-size: 13px;
        padding: 6px 10px;
        border-radius: 6px;
    }}
    QLineEdit#ProjectNameEdit:hover, QLineEdit#ProjectNameEdit:focus {{
        border-color: {p.border};
        color: {p.text};
        background: {p.panel2};
    }}

    /* ---------- Buttons ---------- */
    QPushButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 13px;
        font-weight: 500;
        color: {p.text};
    }}
    QPushButton:hover {{
        background: {p.panel3};
        border-color: {p.border_strong};
    }}
    QPushButton:pressed {{
        background: {p.panel3};
    }}
    QPushButton:disabled {{
        color: {p.text_dimmer};
        border-color: {p.border_soft};
    }}
    QPushButton#PrimaryButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.accent_deep}, stop:1 {p.accent_bright});
        border: none;
        color: white;
        font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.accent_deep_hi}, stop:1 {p.accent_bright_hi});
    }}
    QPushButton#IconButton {{
        padding: 0px;
        min-width: 32px;
        max-width: 32px;
        min-height: 32px;
        max-height: 32px;
        border-radius: 8px;
        qproperty-iconSize: 14px 14px;
    }}
    QPushButton#TimelineIconButton {{
        padding: 0px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 7px;
        qproperty-iconSize: 14px 14px;
    }}
    QPushButton#TrackAddButton {{
        padding: 0px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 7px;
        background: transparent;
        border: 1px solid {p.border};
        qproperty-iconSize: 14px 14px;
    }}
    QPushButton#TrackAddButton:hover {{
        border-color: {p.accent};
        background: {p.panel2};
    }}
    QPushButton#DangerButton:hover {{
        background: {p.danger_soft};
        border-color: #5c2431;
        color: #ff8a9a;
    }}

    /* ---------- Library panel — CapCut icon rail ---------- */
    QFrame#LibraryPanel {{
        background: {p.panel};
        border-right: 1px solid {p.border};
    }}
    QFrame#LibraryTopMenu {{
        background: {p.panel};
        border-bottom: 1px solid {p.border_soft};
    }}
    QScrollArea#LibraryTopMenuScroll {{
        background: transparent;
        border: none;
    }}
    QScrollArea#LibraryTopMenuScroll > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        height: 6px;
        background: transparent;
        margin: 0 6px 2px 6px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.panel3};
        border-radius: 3px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p.border};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        height: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}
    QFrame#LibraryIconButton, QFrame#LibraryTopMenuButton {{
        background: transparent;
        border: none;
        border-radius: 8px;
    }}
    QFrame#LibraryIconButton:hover, QFrame#LibraryTopMenuButton:hover {{
        background: {p.panel2};
    }}
    QFrame#LibraryIconButton[active="true"], QFrame#LibraryTopMenuButton[active="true"] {{
        background: {p.panel2};
    }}
    QLabel#LibraryIconLabel, QLabel#LibraryTopMenuLabel {{
        font-size: 9px;
        font-weight: 600;
        color: {p.text_dimmer};
        background: transparent;
    }}
    QFrame#LibraryIconButton[active="true"] QLabel#LibraryIconLabel,
    QFrame#LibraryTopMenuButton[active="true"] QLabel#LibraryTopMenuLabel {{
        color: {p.accent};
    }}
    QFrame#InspectorTabRow {{
        background: transparent;
        border-bottom: 1px solid {p.border_soft};
        padding: 2px 0 8px 0;
    }}
    QFrame#InspectorTier2TabRow {{
        background: transparent;
        border-bottom: none;
        padding: 0 0 4px 0;
    }}
    QPushButton#InspectorTabButton {{
        background: transparent;
        border: none;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
        color: {p.text_dimmer};
    }}
    QPushButton#InspectorTabButton:hover {{
        color: {p.text_dim};
        background: {p.panel2};
    }}
    QPushButton#InspectorTabButton:checked {{
        color: #ffffff;
        background-color: {p.accent};
        border: none;
    }}
    QPushButton#InspectorTabButton:checked:hover {{
        background-color: {p.accent_hi};
        color: #ffffff;
    }}
    QPushButton#InspectorPresetButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 8px;
        font-size: 11px;
        color: {p.text_dim};
    }}
    QPushButton#InspectorFitButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 0 8px;
        font-size: 11px;
        font-weight: 600;
        color: {p.text_dim};
    }}
    QPushButton#InspectorFitButton:checked {{
        border-color: {p.accent};
        color: #ffffff;
        background-color: {p.accent};
    }}
    QPushButton#InspectorFitButton:checked:hover {{
        background-color: {p.accent_hi};
        border-color: {p.accent_hi};
        color: #ffffff;
    }}
    QPushButton#InspectorFitButton:hover {{
        color: {p.text};
    }}
    QFrame#InspectorFitToolbar {{
        background: {p.panel2};
        border: 1px solid {p.border_soft};
        border-radius: 8px;
    }}
    QFrame#InspectorAlignToolbar {{
        background: {p.panel2};
        border: 1px solid {p.border_soft};
        border-radius: 8px;
    }}
    QPushButton#InspectorAlignButton {{
        background: transparent;
        border: none;
        border-radius: 4px;
        padding: 0;
    }}
    QPushButton#InspectorAlignButton:hover {{
        background: {p.panel};
        color: {p.text};
    }}
    QPushButton#InspectorAlignButton:disabled {{
        color: {p.text_dimmer};
    }}
    QFrame#InspectorAlignSeparator {{
        color: {p.border_soft};
        max-width: 1px;
    }}
    QPushButton#InspectorMaskShapeButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 0;
    }}
    QPushButton#InspectorMaskShapeButton:checked {{
        border-color: {p.accent};
        background-color: {p.accent};
    }}
    QPushButton#InspectorMaskShapeButton:checked:hover {{
        background-color: {p.accent_hi};
        border-color: {p.accent_hi};
    }}
    QFrame#AnimationPresetCard {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 10px;
    }}
    QFrame#AnimationPresetCard[selected="true"] {{
        border-color: {p.accent};
        background-color: {p.accent};
    }}
    QFrame#AnimationPresetCard[selected="true"] QLabel#AnimationPresetName {{
        color: #ffffff;
    }}
    QFrame#AnimationPresetCard:hover {{
        border-color: {p.accent};
    }}
    QLabel#AnimationPresetPreview {{
        border-radius: 8px;
    }}
    QLabel#AnimationPresetName {{
        font-size: 10px;
        color: {p.text_dim};
    }}
    QPushButton#InspectorGhostButton {{
        background: transparent;
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 5px 10px;
        min-height: 28px;
        font-size: 11px;
        font-weight: 600;
        color: {p.text_dim};
    }}
    QPushButton#InspectorGhostButton:hover {{
        border-color: {p.accent};
        color: {p.text};
    }}
    QPushButton#MusicIconButton {{
        background: transparent;
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 0px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
    }}
    QPushButton#MusicIconButton:hover {{
        border-color: {p.accent};
        background: rgba(116, 102, 241, 0.12);
    }}
    QPushButton#MusicIconButtonPrimary {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.accent_deep}, stop:1 {p.accent_bright});
        border: none;
        border-radius: 6px;
        padding: 0px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
    }}
    QPushButton#MusicIconButtonPrimary:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {p.accent_deep_hi}, stop:1 {p.accent_bright_hi});
    }}
    QFrame#LibraryIconRail {{
        background: {p.bg};
        border-right: 1px solid {p.border_soft};
    }}
    QFrame#MusicCategoryRail {{
        background: {p.bg};
        border-right: 1px solid {p.border_soft};
    }}
    QLineEdit#MusicSearchField {{
        min-height: 34px;
        padding: 8px 12px;
        font-size: 12px;
    }}
    QFrame#PlaylistTemplatePreview {{
        background: transparent;
        border: none;
    }}
    QPushButton#CompactImportButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        color: {p.text};
    }}
    QPushButton#CompactImportButton:hover {{
        border-color: {p.accent};
        color: {p.text};
    }}
    QPushButton#CompactImportButton:disabled {{
        color: {p.text_dimmer};
    }}
    QFrame#CapCutImportZone {{
        border: 1px dashed {p.border};
        border-radius: 12px;
        background: {p.panel2};
    }}
    QFrame#CapCutImportZone:hover {{
        border-color: {p.accent};
    }}
    QLabel#CapCutImportTitle {{
        color: {p.text_dim};
        font-size: 13px;
    }}
    QTabBar#MediaSubTabBar::tab {{
        background: transparent;
        color: {p.text_dimmer};
        padding: 8px 14px;
        font-size: 12px;
        font-weight: 600;
        border-bottom: 2px solid transparent;
    }}
    QTabBar#MediaSubTabBar::tab:selected {{
        color: {p.text};
        border-bottom: 2px solid {p.accent};
    }}
    QPushButton#LibraryFooterButton {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 10px 8px;
        font-size: 11px;
        color: {p.text_dim};
    }}
    QPushButton#LibraryFooterButton:hover {{
        border-color: {p.accent};
        color: {p.text};
    }}

    /* Legacy tab widget (unused after rail refactor — kept for tests) */
    QTabBar::tab {{
        background: transparent;
        color: {p.text_dimmer};
        padding: 9px 10px;
        font-size: 12px;
        font-weight: 600;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:hover {{
        color: {p.text_dim};
    }}
    QTabBar::tab:selected {{
        color: {p.text};
        border-bottom: 2px solid {p.accent};
        background: {p.panel2};
    }}
    QTabWidget::pane {{
        border: none;
        background: {p.panel};
    }}
    QFrame#ImportZone {{
        border: 1px dashed {p.border};
        border-radius: 10px;
        padding: 14px 8px;
    }}
    QFrame#ImportZone:hover {{
        border-color: {p.accent};
    }}
    QLabel#SectionTitle {{
        color: {p.text_dimmer};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
    }}
    QLabel#EmptyHint {{
        color: {p.text_dimmer};
        font-size: 12px;
    }}

    /* ---------- Center / preview — CapCut player chrome ---------- */
    QFrame#PreviewHeader {{
        background: {p.panel};
        border-bottom: 1px solid {p.border_soft};
    }}
    QLabel#PreviewHeaderTitle {{
        font-size: 12px;
        font-weight: 600;
        color: {p.text_dim};
    }}
    QFrame#PreviewArea {{
        background: #000000;
    }}
    QFrame#Transport {{
        background: {p.panel};
        border-top: 1px solid {p.border_soft};
    }}
    QLabel#TimeLabel {{
        font-family: "{FONT_MONO}";
        font-size: 12px;
        color: {p.text_dim};
    }}
    QPushButton#PlayButton {{
        background: {p.accent};
        border: none;
        border-radius: 17px;
        min-width: 34px;
        max-width: 34px;
        min-height: 34px;
        max-height: 34px;
        padding: 0px;
        qproperty-iconSize: 14px 14px;
    }}
    QPushButton#PlayButton:hover {{
        background: {p.accent_hi};
    }}
    QPushButton#PreviewControlButton {{
        padding: 0px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 6px;
        background: transparent;
        border: none;
        color: {p.text_dim};
    }}
    QPushButton#PreviewControlButton:hover {{
        background: {p.panel2};
        color: {p.text};
    }}
    QPushButton#PreviewTextControlButton {{
        padding: 0 10px;
        min-width: 52px;
        max-width: 120px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 6px;
        background: transparent;
        border: none;
        color: {p.text_dim};
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton#PreviewTextControlButton:hover {{
        background: {p.panel2};
        color: {p.text};
    }}
    QMenu#CapCutDropdown {{
        background: {p.panel3};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 6px 0;
    }}
    QMenu#CapCutDropdown::separator {{
        height: 1px;
        background: {p.border_soft};
        margin: 4px 10px;
    }}
    QFrame#CapCutMenuRow {{
        background: transparent;
        border: none;
    }}
    QFrame#CapCutMenuRow:hover {{
        background: {p.panel2};
    }}
    QFrame#CapCutMenuRow[disabled="true"] {{
        opacity: 0.45;
    }}
    QLabel#CapCutMenuCheck {{
        color: {p.accent};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel#CapCutMenuLabel {{
        color: {p.text};
        font-size: 13px;
    }}
    QSlider#Scrubber::groove:horizontal {{
        height: 4px;
        background: {p.panel3};
        border-radius: 2px;
    }}
    QSlider#Scrubber::handle:horizontal {{
        background: white;
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
        border: 3px solid {p.accent};
    }}
    QSlider#Scrubber::sub-page:horizontal {{
        background: {p.accent};
        border-radius: 2px;
    }}

    /* ---------- Timeline ---------- */
    QFrame#TimelineWrap {{
        background: {p.panel};
        border-top: 1px solid {p.border};
    }}
    QFrame#TimelineToolbar {{
        border-bottom: 1px solid {p.border_soft};
    }}
    QFrame#TrackHeaders {{
        background: {p.panel};
        border-right: 1px solid {p.border};
    }}
    QLabel#ZoomLabel {{
        color: {p.text_dimmer};
        font-size: 11px;
    }}
    QSlider#ZoomSlider::groove:horizontal {{
        height: 4px;
        background: {p.panel3};
        border-radius: 2px;
    }}
    QSlider#ZoomSlider::handle:horizontal {{
        background: {p.accent};
        width: 10px;
        height: 10px;
        margin: -3px 0;
        border-radius: 5px;
    }}

    /* ---------- Inspector ---------- */
    QFrame#InspectorPanel {{
        background: {p.panel};
        border-left: 1px solid {p.border};
    }}
    QLabel#DetailsFieldValue {{
        font-size: 12px;
        color: {p.text};
    }}
    QLabel#DetailsSectionTitle {{
        font-family: "{FONT_DISPLAY}";
        font-weight: 700;
        font-size: 14px;
        color: {p.text};
    }}
    QLabel#InspTitle {{
        font-family: "{FONT_DISPLAY}";
        font-weight: 700;
        font-size: 14px;
        padding-top: 2px;
    }}
    QLabel#InspSub {{
        font-family: "{FONT_MONO}";
        font-size: 11px;
        color: {p.text_dimmer};
        padding-bottom: 2px;
    }}
    QLabel#FieldLabel {{
        font-size: 11.5px;
        color: {p.text_dim};
        font-weight: 500;
        padding: 0;
    }}
    QCheckBox#InspectorSectionCheck {{
        font-size: 12px;
        font-weight: 600;
        color: {p.text};
        spacing: 8px;
    }}
    QDoubleSpinBox#InspectorValueSpin {{
        background: {p.panel2};
        border: none;
        border-bottom: 1px solid {p.border};
        border-radius: 0;
        padding: 4px 2px;
        font-size: 12px;
        color: {p.text};
    }}
    QDoubleSpinBox#InspectorValueSpin:focus {{
        border-bottom: 1px solid {p.accent};
    }}
    QLineEdit, QTextEdit, QComboBox {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 7px;
        color: {p.text};
        padding: 6px 9px;
        font-size: 12.5px;
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border-color: {p.accent};
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: {p.panel3};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {p.accent};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}
    QSlider::sub-page:horizontal {{
        background: {p.accent};
        border-radius: 2px;
    }}

    /* ---------- Playlist settings sections ---------- */
    QFrame#PlaylistSettingsSection {{
        background: transparent;
        border: 1px solid {p.accent};
        border-radius: 12px;
    }}
    QPushButton#ColorSwatchButton {{
        border: 1px solid {p.border_strong};
        border-radius: 6px;
        padding: 0;
        min-width: 40px;
        min-height: 26px;
        max-width: 40px;
    }}
    QPushButton#ColorSwatchButton:hover {{
        border-color: {p.accent};
    }}
    QPushButton#PlaylistColorFilterChip {{
        border-radius: 8px;
        padding: 0;
    }}

    /* ---------- Music playlist song list ---------- */
    QTableWidget#PlaylistSongList {{
        background: {p.panel2};
        border: 1px solid {p.border};
        border-radius: 8px;
        outline: none;
        padding: 2px;
        gridline-color: transparent;
    }}
    QTableWidget#PlaylistSongList::item {{
        color: {p.text};
        padding: 6px 10px;
        border: none;
        border-radius: 6px;
        margin: 2px 4px;
    }}
    QTableWidget#PlaylistSongList::item:hover {{
        background: rgba(116, 102, 241, 0.16);
        color: {p.text};
    }}
    QTableWidget#PlaylistSongList::item:selected {{
        background: rgba(116, 102, 241, 0.32);
        color: #ffffff;
    }}
    QLabel#PlaylistCoverThumb {{
        background: {p.panel3};
        border: 1px solid {p.border};
        border-radius: 8px;
    }}

    /* ---------- Toast ---------- */
    QLabel#Toast {{
        background: {p.panel2};
        border: 1px solid {p.border};
        color: {p.text};
        padding: 10px 16px;
        border-radius: 9px;
        font-size: 12.5px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.panel3};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.border_strong};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.panel3};
        border-radius: 5px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p.border_strong};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0px;
        height: 0px;
    }}
    """
