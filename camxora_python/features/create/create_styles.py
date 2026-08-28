"""Create workspace QSS — scoped so the rest of the shell is unchanged."""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir

from shared.icons.lucide_icons import lucide_pixmap

# Shared studio tokens. Profile consumes these — do not fork a second palette.
STUDIO_BG = "#071426"
STUDIO_PANEL = "#0D1B2E"
STUDIO_INPUT = "#101F32"
STUDIO_BORDER = "#18304A"
STUDIO_BORDER_STRONG = "#23415E"
STUDIO_TEXT = "#E5EDF7"
STUDIO_TEXT_MUTED = "#8FA4BB"
STUDIO_TEXT_DIM = "#60758C"
STUDIO_PURPLE = "#6335D9"
STUDIO_PURPLE_BRIGHT = "#7C3AED"
STUDIO_SUCCESS = "#00C878"
STUDIO_WARNING = "#F59E0B"
STUDIO_TABLE = "#071522"
STUDIO_TABLE_ALT = "#081828"
STUDIO_AVATAR_COLORS = (
    "#6335D9",
    "#7C3AED",
    "#38BDF8",
    "#00C878",
    "#F59E0B",
    "#EC4899",
    "#14B8A6",
    "#6366F1",
)

CREATE_PAGE_QSS = """
QWidget#create_workspace,
QWidget#create_workspace QLabel,
QWidget#create_workspace QPushButton,
QWidget#create_workspace QToolButton,
QWidget#create_workspace QLineEdit,
QWidget#create_workspace QComboBox,
QWidget#create_workspace QDateEdit,
QWidget#create_workspace QSpinBox,
QWidget#create_workspace QTextEdit,
QWidget#create_workspace QCheckBox,
QWidget#create_workspace QRadioButton,
QWidget#create_workspace QTableWidget,
QWidget#create_workspace QHeaderView::section {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
}

QWidget#create_workspace QTextEdit,
QWidget#create_workspace QLineEdit,
QWidget#create_workspace QTableWidget,
QWidget#create_workspace QTableWidget::item,
QWidget#create_workspace QLabel#TrackTitle {
    font-family: 'Khmer OS Siemreap', 'Khmer OS Siem reap', 'Inter', 'Segoe UI', Arial, sans-serif;
}

QWidget#create_workspace {
    background-color: #071426;
    color: #E5EDF7;
    font-size: 12px;
}

QWidget#create_workspace QSplitter::handle {
    background-color: #071426;
    width: 10px;
}

QWidget#create_workspace QFrame#CreateHeader,
QWidget#create_workspace QFrame#PlanningBar,
QWidget#create_workspace QFrame#Panel,
QWidget#create_workspace QFrame#Player {
    background-color: #0D1B2E;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#create_workspace QLabel#PageTitle {
    color: #E5EDF7;
    font-size: 21px;
    font-weight: 600;
    background: transparent;
}

QWidget#create_workspace QLabel#PageSubtitle {
    color: #8FA4BB;
    font-size: 12px;
    background: transparent;
}

QWidget#create_workspace QLabel#PlanMeta {
    color: #60758C;
    font-size: 12px;
    background: transparent;
}

QWidget#create_workspace QLabel#FieldLabel,
QWidget#create_workspace QLabel#SectionLabel {
    color: #8FA4BB;
    font-size: 12px;
    font-weight: 500;
    background: transparent;
}

QWidget#create_workspace QLabel#SectionLabel {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.1px;
}

QWidget#create_workspace QPushButton#SecondaryButton,
QWidget#create_workspace QToolButton#SecondaryButton {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #23415E;
    border-radius: 5px;
    padding: 0 10px;
    font-size: 12px;
    font-weight: 500;
    min-height: 28px;
    max-height: 28px;
}

QWidget#create_workspace QPushButton#SecondaryButton:hover {
    border-color: #7C3AED;
    color: #ffffff;
}

QWidget#create_workspace QToolButton#FilesRefresh,
QWidget#create_workspace QToolButton#DateCalendarButton {
    background: transparent;
    border: none;
    padding: 0;
}

QWidget#create_workspace QToolButton#FilesRefresh:hover,
QWidget#create_workspace QToolButton#DateCalendarButton:hover {
    background: transparent;
    border: none;
}

QWidget#create_workspace QLineEdit,
QWidget#create_workspace QComboBox,
QWidget#create_workspace QDateEdit,
QWidget#create_workspace QSpinBox {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    padding: 0 8px;
    min-height: 28px;
    max-height: 28px;
    font-size: 12px;
    selection-background-color: #6335D9;
}

QWidget#create_workspace QComboBox,
QWidget#create_workspace QDateEdit {
    padding-right: 26px;
}

QWidget#create_workspace QLineEdit:focus,
QWidget#create_workspace QComboBox:focus,
QWidget#create_workspace QDateEdit:focus,
QWidget#create_workspace QSpinBox:focus,
QWidget#create_workspace QTextEdit:focus {
    border: 1px solid #7C3AED;
}

QWidget#create_workspace QLineEdit::placeholder,
QWidget#create_workspace QTextEdit::placeholder {
    color: #60758C;
}

QWidget#create_workspace QComboBox::drop-down,
QWidget#create_workspace QDateEdit::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    background: transparent;
    width: 0;
}

QWidget#create_workspace QComboBox::down-arrow,
QWidget#create_workspace QDateEdit::down-arrow {
    image: none;
    border: none;
    width: 0;
    height: 0;
}

QWidget#create_workspace QComboBox QAbstractItemView {
    background-color: #0D1B2E;
    color: #E5EDF7;
    border: 1px solid #23415E;
    selection-background-color: #6335D9;
    outline: none;
    font-size: 12px;
}

QWidget#create_workspace QSpinBox::up-button,
QWidget#create_workspace QSpinBox::down-button {
    background: transparent;
    border: none;
    width: 16px;
}

QWidget#create_workspace QWidget#EditorPair,
QWidget#create_workspace QWidget#EditorBlock,
QWidget#create_workspace QWidget#TransparentBlock {
    background: transparent;
    border: none;
}

QWidget#create_workspace QTextEdit {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    padding: 8px 10px 22px 10px;
    font-size: 12px;
}

QWidget#create_workspace QTextEdit QWidget {
    background-color: #101F32;
}

QWidget#create_workspace QLabel#CharCount {
    color: #60758C;
    font-size: 12px;
    background: transparent;
}

QWidget#create_workspace QPushButton#ModeTab {
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 0 12px;
}

QWidget#create_workspace QPushButton#ModeTab:hover,
QWidget#create_workspace QPushButton#ModeTab:pressed,
QWidget#create_workspace QPushButton#ModeTab:checked {
    background: transparent;
    border: none;
}

QWidget#create_workspace QFrame#ModeTabBar {
    background-color: #071426;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#create_workspace QCheckBox,
QWidget#create_workspace QRadioButton {
    color: #E5EDF7;
    font-size: 12px;
    spacing: 8px;
    background: transparent;
}

QWidget#create_workspace QCheckBox::indicator,
QWidget#create_workspace QRadioButton::indicator {
    width: 0;
    height: 0;
    border: none;
    background: transparent;
}

QWidget#create_workspace QSlider::groove:horizontal {
    height: 4px;
    background: #18304A;
    border-radius: 2px;
}

QWidget#create_workspace QSlider::sub-page:horizontal {
    background: #7C3AED;
    border-radius: 2px;
}

QWidget#create_workspace QSlider::add-page:horizontal {
    background: #18304A;
    border-radius: 2px;
}

QWidget#create_workspace QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #7C3AED;
    border: 2px solid #C4B5FD;
    border-radius: 7px;
}

QWidget#create_workspace QTableWidget,
QWidget#create_workspace QTableView {
    background-color: #071522;
    alternate-background-color: #081828;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    gridline-color: #18304A;
    font-size: 15px;
    outline: none;
}

QWidget#create_workspace QTableWidget::item,
QWidget#create_workspace QTableView::item {
    padding: 2px 6px;
    border-bottom: 1px solid #18304A;
}

QWidget#create_workspace QTableWidget::item:selected,
QWidget#create_workspace QTableView::item:selected {
    background-color: rgba(99, 53, 217, 0.28);
    color: #E5EDF7;
}

QWidget#create_workspace QProgressBar {
    background-color: #18304A;
    border: none;
    border-radius: 2px;
    min-height: 4px;
    max-height: 6px;
    text-align: center;
}

QWidget#create_workspace QProgressBar::chunk {
    background-color: #7C3AED;
    border-radius: 2px;
}

QWidget#create_workspace QHeaderView::section {
    background-color: #0D1B2E;
    color: #60758C;
    border: none;
    border-bottom: 1px solid #18304A;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
}

QWidget#create_workspace QLabel#StatusBadge {
    background-color: #00C878;
    color: #ffffff;
    border: none;
    border-radius: 3px;
    padding: 0 7px;
    min-height: 16px;
    max-height: 16px;
    font-size: 10px;
    font-weight: 600;
}

QWidget#create_workspace QPushButton#Transport {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #23415E;
    border-radius: 5px;
    min-height: 26px;
    max-height: 26px;
    padding: 0 12px;
    font-size: 12px;
}

QWidget#create_workspace QPushButton#TransportPrimary {
    background-color: #6335D9;
    color: #ffffff;
    border: 1px solid #7C3AED;
    border-radius: 5px;
    min-height: 26px;
    max-height: 26px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 600;
}

QWidget#create_workspace QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px;
}

QWidget#create_workspace QScrollBar::handle:vertical {
    background: #23415E;
    border-radius: 3px;
    min-height: 24px;
}
"""


def studio_workspace_qss(scope: str) -> str:
    """Create-page QSS remapped onto another workspace objectName."""
    return CREATE_PAGE_QSS.replace("#create_workspace", f"#{scope}")


def _icon_url(name: str, size: int, color: str) -> str:
    cache = Path(gettempdir()) / "camxora_create_icons"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{name}_{size}_{color.lstrip('#')}.png"
    if not path.exists():
        lucide_pixmap(name, size=size, color=color).save(str(path), "PNG")
    return str(path.resolve()).replace("\\", "/")


def build_create_page_qss() -> str:
    from shared.lib.ui_font import ensure_khmer_siemreap_loaded

    family = ensure_khmer_siemreap_loaded()
    up = _icon_url("chevron-up", 10, "#8FA4BB")
    down = _icon_url("chevron-down", 10, "#8FA4BB")
    return studio_workspace_qss("create_workspace") + f"""
QWidget#create_workspace QSpinBox::up-arrow {{
    image: url("{up}");
    width: 10px;
    height: 10px;
}}
QWidget#create_workspace QSpinBox::down-arrow {{
    image: url("{down}");
    width: 10px;
    height: 10px;
}}
QWidget#create_workspace QTextEdit,
QWidget#create_workspace QLineEdit#SongTitle,
QWidget#create_workspace QLineEdit#NegativeTags,
QWidget#create_workspace QTableWidget#FileTable,
QWidget#create_workspace QTableWidget#FileTable::item,
QWidget#create_workspace QLabel#TrackTitle {{
    font-family: '{family}', 'Inter', 'Segoe UI', Arial, sans-serif;
}}
QWidget#create_workspace QLabel#TrackTitle {{
    color: #8FA4BB;
    font-size: 12px;
    background: transparent;
}}
"""
