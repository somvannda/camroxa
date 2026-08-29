"""Image QSS — Create studio stylesheet plus Image-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

IMAGE_EXTRAS = """
QWidget#image_workspace,
QWidget#image_workspace QScrollArea,
QScrollArea#image_workspace,
QScrollArea#image_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#image_workspace QFrame#Panel,
QWidget#image_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#image_workspace QFrame#NestedPanel {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#image_workspace QFrame#image_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#image_workspace QLabel#image_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}

QWidget#image_workspace QLabel#image_warning_text {
    color: #FCD34D;
    font-size: 12px;
    background: transparent;
}

QWidget#image_workspace QLabel#ImageStatValue {
    color: #E5EDF7;
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}

QWidget#image_workspace QLabel#ImageStatValue[tone="success"] {
    color: #22C55E;
}

QWidget#image_workspace QLabel#ImageStatValue[tone="warning"] {
    color: #F59E0B;
}

QWidget#image_workspace QLabel#ImageStatValue[tone="danger"] {
    color: #EF4444;
}

QWidget#image_workspace QLabel#ImageStatValue[tone="active"] {
    color: #38BDF8;
}

QWidget#image_workspace QFrame#ImageAlbumCard,
QWidget#image_workspace QFrame#OutlinePanel {
    background-color: transparent;
    border: none;
}

QWidget#image_workspace QLabel#ImageSelectedTitle {
    color: #E5EDF7;
    font-size: 15px;
    font-weight: 600;
    background: transparent;
}

QWidget#image_workspace QLabel#ImageStatusBadge {
    color: #8FA4BB;
    font-size: 10px;
    font-weight: 600;
    border-radius: 3px;
    padding: 2px 8px;
    min-height: 16px;
    max-height: 18px;
    background-color: #23415E;
}

QWidget#image_workspace QLabel#ImageStatusBadge[tone="success"] {
    background-color: #065F46;
    color: #6EE7B7;
}

QWidget#image_workspace QLabel#ImageStatusBadge[tone="warning"] {
    background-color: #78350F;
    color: #FCD34D;
}

QWidget#image_workspace QLabel#ImageStatusBadge[tone="danger"] {
    background-color: #7F1D1D;
    color: #FCA5A5;
}

QWidget#image_workspace QLabel#ImageStatusBadge[tone="active"] {
    background-color: #0E3A4A;
    color: #7DD3FC;
}

QWidget#image_workspace QSplitter::handle {
    background-color: #071426;
    width: 6px;
}

QWidget#image_workspace QLabel#image_preview_stage {
    background-color: #101F32;
    color: #8FA4BB;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
}

QWidget#image_workspace QTableWidget#image_queue_table {
    background-color: #071522;
    alternate-background-color: #081828;
    gridline-color: #18304A;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
    selection-background-color: #6335D9;
    selection-color: #ffffff;
}

QWidget#image_workspace QTableWidget#image_queue_table::item {
    padding: 2px 6px;
}

QWidget#image_workspace QTableWidget#image_queue_table::item:selected {
    background-color: #6335D9;
    color: #ffffff;
}

QWidget#image_workspace QHeaderView::section {
    font-size: 12px;
}

QWidget#image_workspace QTextEdit#shell_text_edit {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    padding: 8px 10px;
    font-size: 12px;
}
"""


def build_image_page_qss() -> str:
    return studio_workspace_qss("image_workspace") + IMAGE_EXTRAS
