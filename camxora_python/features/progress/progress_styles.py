"""Progress QSS — Create studio stylesheet plus Progress-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

PROGRESS_EXTRAS = """
QWidget#progress_workspace,
QWidget#progress_workspace QScrollArea,
QScrollArea#progress_workspace,
QScrollArea#progress_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#progress_workspace QSplitter::handle {
    background-color: #071426;
    width: 6px;
}

QWidget#progress_workspace QScrollArea#ProgressDetailScroll,
QWidget#progress_workspace QScrollArea#ProgressDetailScroll > QWidget,
QWidget#progress_workspace QWidget#ProgressDetailBody,
QWidget#progress_workspace QWidget#ProgressDetailContent {
    background: transparent;
    border: none;
}

QWidget#progress_workspace QFrame#Panel,
QWidget#progress_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#progress_workspace QLabel#KpiValue {
    color: #E5EDF7;
    font-size: 20px;
    font-weight: 600;
    background: transparent;
}

QWidget#progress_workspace QFrame#NestedPanel {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#progress_workspace QFrame#progress_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#progress_workspace QLabel#progress_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}

QWidget#progress_workspace QLabel#progress_warning_text {
    color: #FCD34D;
    font-size: 12px;
    background: transparent;
}

QWidget#progress_workspace QTableWidget#ProgressTable {
    background-color: #071522;
    alternate-background-color: #081828;
    gridline-color: #18304A;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
    selection-background-color: rgba(99, 53, 217, 0.28);
    selection-color: #E5EDF7;
}

QWidget#progress_workspace QTableWidget#ProgressTable::item {
    padding: 2px 6px;
}

QWidget#progress_workspace QTableWidget#ProgressTable::item:hover {
    background-color: rgba(99, 53, 217, 0.12);
}

QWidget#progress_workspace QTableWidget#ProgressTable::item:selected {
    background-color: rgba(99, 53, 217, 0.28);
    color: #E5EDF7;
}

QWidget#progress_workspace QLabel#ProgressCellValue {
    color: #E5EDF7;
    font-size: 11px;
    background: transparent;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar {
    background-color: #18304A;
    border: none;
    border-radius: 2px;
    min-height: 3px;
    max-height: 3px;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar::chunk {
    background-color: #7C3AED;
    border-radius: 2px;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar[tone="success"]::chunk {
    background-color: #00C878;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar[tone="warning"]::chunk {
    background-color: #F59E0B;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar[tone="danger"]::chunk {
    background-color: #F43F5E;
}

QWidget#progress_workspace QProgressBar#ProgressCellBar[tone="muted"]::chunk {
    background-color: #23415E;
}

QWidget#progress_workspace QHeaderView::section {
    font-size: 12px;
}

QWidget#progress_workspace QLabel#ProgressDetailTitle {
    color: #E5EDF7;
    font-size: 16px;
    font-weight: 600;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailMeta {
    color: #8FA4BB;
    font-size: 11px;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailState {
    color: #7C3AED;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailSection {
    color: #60758C;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailEmpty {
    color: #8FA4BB;
    font-size: 12px;
    background: transparent;
}

QWidget#progress_workspace QFrame#ProgressDetailRule {
    color: #1C3A5B;
    background-color: #1C3A5B;
    max-height: 1px;
    border: none;
}

QWidget#progress_workspace QLabel#ProgressDetailStepLabel {
    color: #60758C;
    font-size: 10px;
    font-weight: 600;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailStepValue {
    color: #E5EDF7;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailStepHint {
    color: #8FA4BB;
    font-size: 11px;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus {
    color: #8FA4BB;
    font-size: 10px;
    font-weight: 600;
    border-radius: 3px;
    padding: 2px 8px;
    min-height: 16px;
    max-height: 18px;
    background-color: #23415E;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus[tone="success"] {
    background-color: #065F46;
    color: #6EE7B7;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus[tone="warning"] {
    background-color: #78350F;
    color: #FCD34D;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus[tone="danger"] {
    background-color: #7F1D1D;
    color: #FCA5A5;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus[tone="muted"] {
    background-color: #23415E;
    color: #8FA4BB;
}

QWidget#progress_workspace QLabel#ProgressDetailStatus[tone="active"] {
    background-color: #0E3A4A;
    color: #7DD3FC;
}

QWidget#progress_workspace QFrame#ProgressDetailContext {
    background-color: #101D31;
    border: 1px solid #1C3A5B;
    border-radius: 5px;
}

QWidget#progress_workspace QFrame#ProgressDetailContext[kind="waiting"] {
    background-color: #16122A;
    border: 1px solid #3B2A6A;
}

QWidget#progress_workspace QFrame#ProgressDetailContext[kind="failed"],
QWidget#progress_workspace QFrame#ProgressDetailContext[kind="blocked"] {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
}

QWidget#progress_workspace QFrame#ProgressDetailContext[kind="completed"] {
    background-color: #0F241C;
    border: 1px solid #14532D;
}

QWidget#progress_workspace QLabel#ProgressDetailContextTitle {
    color: #8FA4BB;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    background: transparent;
}

QWidget#progress_workspace QLabel#ProgressDetailNoticeText {
    color: #C4D4E6;
    font-size: 11px;
    background: transparent;
}

QWidget#progress_workspace QFrame#ProgressDetailPath {
    background-color: #101F32;
    border: 1px solid #18304A;
    border-radius: 5px;
}

QWidget#progress_workspace QLabel#ProgressDetailPathText {
    color: #8FA4BB;
    font-size: 11px;
    background: transparent;
}
"""


def build_progress_page_qss() -> str:
    return studio_workspace_qss("progress_workspace") + PROGRESS_EXTRAS
