"""Workflow QSS — Create studio stylesheet plus Workflow-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

WORKFLOW_EXTRAS = """
QWidget#workflow_workspace,
QWidget#workflow_workspace QScrollArea,
QScrollArea#workflow_workspace,
QScrollArea#workflow_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#workflow_workspace QFrame#Panel,
QWidget#workflow_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#workflow_workspace QLabel#KpiValue {
    color: #E5EDF7;
    font-size: 20px;
    font-weight: 600;
    background: transparent;
}

QWidget#workflow_workspace QListWidget#workflow_lane_list {
    background-color: #071522;
    alternate-background-color: #081828;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
    outline: none;
}

QWidget#workflow_workspace QListWidget#workflow_lane_list::item {
    padding: 8px 10px;
    border-bottom: 1px solid #18304A;
}

QWidget#workflow_workspace QListWidget#workflow_lane_list::item:selected {
    background-color: #6335D9;
    color: #ffffff;
}

QWidget#workflow_workspace QListWidget#workflow_lane_list::item:hover {
    background-color: rgba(99, 53, 217, 0.22);
}

QWidget#workflow_workspace QLabel#StatusBadge {
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

QWidget#workflow_workspace QFrame#workflow_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#workflow_workspace QLabel#workflow_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}
"""


def build_workflow_page_qss() -> str:
    return studio_workspace_qss("workflow_workspace") + WORKFLOW_EXTRAS
