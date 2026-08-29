"""Dashboard QSS — Create studio stylesheet plus Dashboard-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

DASHBOARD_EXTRAS = """
QWidget#dashboard_workspace,
QWidget#dashboard_workspace QScrollArea,
QScrollArea#dashboard_workspace,
QScrollArea#dashboard_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#dashboard_workspace QFrame#Panel,
QWidget#dashboard_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#dashboard_workspace QLabel#KpiValue {
    color: #E5EDF7;
    font-size: 20px;
    font-weight: 600;
    background: transparent;
}

QWidget#dashboard_workspace QLabel#KpiDeltaUp {
    color: #00C878;
    font-size: 11px;
    background: transparent;
}

QWidget#dashboard_workspace QLabel#KpiDeltaDown {
    color: #F43F5E;
    font-size: 11px;
    background: transparent;
}

QWidget#dashboard_workspace QLabel#KpiDeltaFlat {
    color: #60758C;
    font-size: 11px;
    background: transparent;
}

QWidget#dashboard_workspace QFrame#NestedPanel {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#dashboard_workspace QFrame#dashboard_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#dashboard_workspace QLabel#dashboard_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}

QWidget#dashboard_workspace QTableView#ChannelTable,
QWidget#dashboard_workspace QTableWidget#ActivityTable {
    background-color: #071522;
    alternate-background-color: #081828;
    gridline-color: #18304A;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
    selection-background-color: #6335D9;
    selection-color: #ffffff;
}

QWidget#dashboard_workspace QTableView#ChannelTable::item,
QWidget#dashboard_workspace QTableWidget#ActivityTable::item {
    padding: 2px 6px;
}

QWidget#dashboard_workspace QTableView#ChannelTable::item:selected,
QWidget#dashboard_workspace QTableWidget#ActivityTable::item:selected {
    background-color: #6335D9;
    color: #ffffff;
}

QWidget#dashboard_workspace QHeaderView::section {
    font-size: 12px;
}
"""


def build_dashboard_page_qss() -> str:
    return studio_workspace_qss("dashboard_workspace") + DASHBOARD_EXTRAS
