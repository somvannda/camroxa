"""Video QSS — Create studio stylesheet plus Video-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

VIDEO_EXTRAS = """
QWidget#video_workspace,
QWidget#video_workspace QScrollArea,
QScrollArea#video_workspace,
QScrollArea#video_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#video_workspace QFrame#Panel,
QWidget#video_workspace QFrame#CreateHeader,
QWidget#video_workspace QFrame#account_card {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#video_workspace QFrame#account_card QFrame#account_card {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#video_workspace QFrame#account_card .QWidget,
QWidget#video_workspace QFrame#account_card QCheckBox,
QWidget#video_workspace QFrame#account_card QSlider {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QPushButton#settings_secondary_button {
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

QWidget#video_workspace QPushButton#settings_secondary_button:hover {
    border-color: #7C3AED;
    color: #ffffff;
}

QWidget#video_workspace QPushButton#settings_secondary_button:pressed {
    background-color: #0A1628;
}

QWidget#video_workspace QPushButton#settings_secondary_button:disabled {
    background-color: #0A1628;
    color: #60758C;
    border-color: #18304A;
}

QWidget#video_workspace QPushButton#start_button,
QWidget#video_workspace QPushButton#TransportPrimary {
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

QWidget#video_workspace QPushButton#start_button:hover,
QWidget#video_workspace QPushButton#TransportPrimary:hover {
    background-color: #7C3AED;
}

QWidget#video_workspace QPushButton#start_button:disabled,
QWidget#video_workspace QPushButton#TransportPrimary:disabled {
    background-color: #2A1B4A;
    border-color: #3B2A6A;
    color: #8FA4BB;
}

QWidget#video_workspace QTabWidget::pane {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QTabBar::tab {
    background-color: #101F32;
    color: #8FA4BB;
    border: 1px solid #18304A;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    min-height: 24px;
}

QWidget#video_workspace QTabBar::tab:hover {
    color: #E5EDF7;
    border-color: #23415E;
}

QWidget#video_workspace QTabBar::tab:selected {
    background-color: #6335D9;
    color: #ffffff;
    border-color: #6335D9;
}

QWidget#video_workspace QFrame#video_export_fields {
    background-color: transparent;
    border: none;
}

QWidget#video_workspace QFrame#video_export_fields QComboBox,
QWidget#video_workspace QFrame#video_export_fields QSpinBox,
QWidget#video_workspace QFrame#video_export_fields QDoubleSpinBox {
    background-color: #101F32;
    border: 1px solid #18304A;
    border-radius: 5px;
    min-height: 24px;
    max-height: 26px;
    min-width: 100px;
    padding: 0px 4px;
    padding-right: 18px;
    color: #E5EDF7;
    font-size: 12px;
}

QWidget#video_workspace QFrame#video_export_fields QComboBox QAbstractItemView {
    background-color: #0A1628;
    border: 1px solid #18304A;
    color: #E5EDF7;
    outline: none;
    min-width: 140px;
    font-size: 12px;
}

QWidget#video_workspace QListWidget#video_export_track_list {
    background-color: #071522;
    border: 1px solid #18304A;
    border-radius: 5px;
    outline: none;
    color: #E5EDF7;
    font-size: 12px;
}

QWidget#video_workspace QListWidget#video_export_track_list::item {
    padding: 6px 8px;
    border: none;
    border-radius: 3px;
    color: #E5EDF7;
    outline: none;
}

QWidget#video_workspace QListWidget#video_export_track_list::item:selected,
QWidget#video_workspace QListWidget#video_export_track_list::item:selected:active,
QWidget#video_workspace QListWidget#video_export_track_list::item:selected:!active {
    background-color: #6335D9;
    color: #ffffff;
    border: none;
    outline: none;
}

QWidget#video_workspace QListWidget#video_export_track_list::item:hover:!selected {
    background-color: rgba(99, 53, 217, 0.22);
}

QWidget#video_workspace QProgressBar {
    background-color: #101F32;
    border: 1px solid #18304A;
    border-radius: 4px;
}

QWidget#video_workspace QProgressBar::chunk {
    background-color: #6335D9;
    border-radius: 3px;
}
"""


def build_video_page_qss() -> str:
    return studio_workspace_qss("video_workspace") + VIDEO_EXTRAS
