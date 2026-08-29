"""Settings QSS — Create studio stylesheet plus Settings-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

SETTINGS_EXTRAS = """
QWidget#settings_workspace,
QWidget#settings_workspace QScrollArea,
QScrollArea#settings_workspace,
QScrollArea#settings_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#settings_workspace QFrame#Panel,
QWidget#settings_workspace QFrame#CreateHeader,
QWidget#settings_workspace QFrame#account_card,
QWidget#settings_workspace QFrame#settings_footer,
QWidget#settings_workspace QFrame#settings_footer_success,
QWidget#settings_workspace QFrame#settings_footer_warning,
QWidget#settings_workspace QFrame#settings_footer_error {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#settings_workspace QFrame#settings_footer_success {
    border-color: #065F46;
}

QWidget#settings_workspace QFrame#settings_footer_warning {
    border-color: #78350F;
}

QWidget#settings_workspace QFrame#settings_footer_error {
    border-color: #7F1D1D;
}

QWidget#settings_workspace QPushButton#FilterChip {
    background-color: #101F32;
    color: #8FA4BB;
    border: 1px solid #18304A;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    min-height: 28px;
    max-height: 28px;
}

QWidget#settings_workspace QPushButton#FilterChip:hover {
    border-color: #23415E;
    color: #E5EDF7;
}

QWidget#settings_workspace QPushButton#FilterChip:checked {
    background-color: #6335D9;
    color: #ffffff;
    border-color: #6335D9;
}

QWidget#settings_workspace QFrame#settings_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#settings_workspace QLabel#settings_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}

QWidget#settings_workspace QListWidget {
    background-color: #071522;
    alternate-background-color: #081828;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
    outline: none;
}

QWidget#settings_workspace QListWidget::item:selected {
    background-color: #6335D9;
    color: #ffffff;
}

QWidget#settings_workspace QListWidget::item:hover {
    background-color: rgba(99, 53, 217, 0.22);
}
"""


def build_settings_page_qss() -> str:
    return studio_workspace_qss("settings_workspace") + SETTINGS_EXTRAS
