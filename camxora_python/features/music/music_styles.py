"""Music QSS — Create studio stylesheet plus Music-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

MUSIC_EXTRAS = """
QWidget#music_workspace,
QWidget#music_workspace QScrollArea,
QScrollArea#music_workspace,
QScrollArea#music_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#music_workspace QFrame#Panel,
QWidget#music_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#music_workspace QFrame#NestedPanel {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#music_workspace QFrame#music_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#music_workspace QLabel#music_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}

QWidget#music_workspace QLabel#music_warning_text {
    color: #FCD34D;
    font-size: 12px;
    background: transparent;
}

QWidget#music_workspace QPushButton#start_button {
    background-color: #6335D9;
    color: #ffffff;
    border: 1px solid #7C3AED;
    border-radius: 5px;
    min-height: 36px;
    max-height: 36px;
    padding: 0 14px;
    font-size: 12px;
    font-weight: 600;
}

QWidget#music_workspace QPushButton#start_button:hover {
    background-color: #7C3AED;
}

QWidget#music_workspace QPushButton#start_button:disabled {
    background-color: #101F32;
    color: #60758C;
    border-color: #18304A;
}

QWidget#music_workspace QPushButton#ChannelChip {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #23415E;
    border-radius: 5px;
    min-height: 26px;
    max-height: 26px;
    padding: 0 8px;
    font-size: 12px;
    text-align: left;
}

QWidget#music_workspace QPushButton#ChannelChip:checked {
    background-color: #6335D9;
    color: #ffffff;
    border-color: #7C3AED;
}

QWidget#music_workspace QTableWidget#history_data_table {
    background-color: #071522;
    alternate-background-color: #081828;
    gridline-color: #18304A;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
}

QWidget#music_workspace QTableWidget#history_data_table::item {
    padding: 2px 6px;
}

QWidget#music_workspace QHeaderView::section {
    font-size: 12px;
}

QWidget#music_workspace QTextEdit#shell_text_edit {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    padding: 8px 10px;
    font-size: 12px;
}

QWidget#music_workspace QFrame#music_plan_summary {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#music_workspace QLabel#music_plan_summary_text {
    color: #8FA4BB;
    font-size: 12px;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanMetricValue {
    color: #E5EDF7;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanCreditTotal {
    color: #00C878;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanCreditDraft {
    color: #A78BFA;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanCreditSuno {
    color: #38BDF8;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanCreditImage {
    color: #00C878;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QWidget#music_workspace QLabel#PlanCreditVideo {
    color: #14B8A6;
    font-size: 14px;
    font-weight: 700;
    background: transparent;
}

QWidget#music_workspace QFrame#PlanDashRule {
    background: transparent;
    border: none;
    border-top: 1px dashed #23415E;
}

QWidget#music_workspace QFrame#PlanColumnRule {
    background: #18304A;
    border: none;
    max-width: 1px;
}
"""


def build_music_page_qss() -> str:
    return studio_workspace_qss("music_workspace") + MUSIC_EXTRAS
