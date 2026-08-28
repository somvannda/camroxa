"""Profile QSS — Create studio stylesheet plus Profile-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

# Profile-only selectors, using the same Create colors and control sizes.
PROFILE_EXTRAS = """
QWidget#profile_workspace,
QWidget#profile_workspace QScrollArea,
QScrollArea#profile_workspace,
QScrollArea#profile_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#profile_workspace QFrame#Panel,
QWidget#profile_workspace QFrame#CreateHeader {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#profile_workspace QTableView,
QWidget#profile_workspace QTableView::item {
    font-size: 12px;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
    selection-background-color: #6335D9;
    selection-color: #E5EDF7;
}

QWidget#profile_workspace QTableView#ProfileTable::item:selected {
    background-color: #6335D9;
    color: #E5EDF7;
}

QWidget#profile_workspace QFrame#InfoGrid {
    background-color: #18304A;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#profile_workspace QWidget#InfoField {
    background-color: #0A1628;
    border: none;
}

QWidget#profile_workspace QLabel#InfoLabel,
QWidget#profile_workspace QLabel#AddonLabel {
    color: #60758C;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.6px;
    background: transparent;
}

QWidget#profile_workspace QLabel#InfoValue,
QWidget#profile_workspace QLabel#AddonValue,
QWidget#profile_workspace QLabel#ActivityDetail,
QWidget#profile_workspace QLabel#ActivityTime {
    color: #E5EDF7;
    font-size: 12px;
    background: transparent;
}

QWidget#profile_workspace QLabel#ActivityDetail,
QWidget#profile_workspace QLabel#ActivityTime {
    color: #8FA4BB;
}

QWidget#profile_workspace QLabel#InfoValueSuccess {
    color: #00C878;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

QWidget#profile_workspace QFrame#MetricCard {
    background-color: #0A1628;
    border: 1px solid #18304A;
    border-radius: 6px;
}

QWidget#profile_workspace QPushButton#ActivityLink {
    background: transparent;
    color: #8B5CF6;
    border: 1px solid #18304A;
    border-radius: 5px;
    min-height: 28px;
    max-height: 28px;
    font-size: 12px;
    font-weight: 600;
}

QWidget#profile_workspace QPushButton#ActivityLink:hover {
    border-color: #7C3AED;
    color: #C4B5FD;
}

QWidget#profile_workspace QLabel#DisplayName,
QWidget#profile_workspace QLabel#ActivityTitle {
    color: #E5EDF7;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QWidget#profile_workspace QLabel#AccountEmail,
QWidget#profile_workspace QLabel#AccountPlan,
QWidget#profile_workspace QLabel#PlanSubtitle,
QWidget#profile_workspace QLabel#SectionHint,
QWidget#profile_workspace QLabel#MetricCaption {
    color: #8FA4BB;
    font-size: 12px;
    background: transparent;
}

QWidget#profile_workspace QLabel#PlanName,
QWidget#profile_workspace QLabel#AllowanceLabel {
    color: #E5EDF7;
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}

QWidget#profile_workspace QLabel#MetricValue {
    color: #E5EDF7;
    font-size: 18px;
    font-weight: 600;
    background: transparent;
}

QWidget#profile_workspace QWidget#Toolbar {
    background: transparent;
    border: none;
}

QWidget#profile_workspace QLabel#StatusBadge,
QWidget#profile_workspace QLabel#VerifiedBadge {
    background-color: #00C878;
    color: #ffffff;
    border: none;
    border-radius: 3px;
    padding: 2px 8px;
    min-height: 20px;
    max-height: 20px;
    font-size: 10px;
    font-weight: 600;
}

QWidget#profile_workspace QPushButton#PageButton {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #23415E;
    border-radius: 5px;
    padding: 0;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    font-size: 12px;
    font-weight: 600;
}

QWidget#profile_workspace QPushButton#PageButton:checked,
QWidget#profile_workspace QPushButton#PageButton:hover {
    border-color: #7C3AED;
    color: #ffffff;
}

QWidget#profile_workspace QPushButton#PageButton:checked {
    background-color: #6335D9;
}

QWidget#profile_workspace QToolButton#RowAction,
QWidget#profile_workspace QToolButton#HeaderGear {
    background: transparent;
    border: none;
}

QWidget#profile_workspace QFrame#ActivityItem {
    background: transparent;
    border: none;
    border-bottom: 1px solid #18304A;
}

QWidget#profile_workspace QMenu {
    background-color: #0D1B2E;
    color: #E5EDF7;
    border: 1px solid #23415E;
}

QWidget#profile_workspace QMenu::item {
    padding: 6px 14px;
}

QWidget#profile_workspace QMenu::item:selected {
    background-color: rgba(99, 53, 217, 0.28);
}

QDialog#profile_dialog {
    background-color: #071426;
    color: #E5EDF7;
}

QDialog#profile_dialog QLabel {
    color: #8FA4BB;
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
}

QDialog#profile_dialog QLineEdit,
QDialog#profile_dialog QComboBox {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    min-height: 28px;
    max-height: 28px;
    padding: 0 8px;
}

QDialog#profile_dialog QLineEdit:focus,
QDialog#profile_dialog QComboBox:focus {
    border: 1px solid #7C3AED;
}

QDialog#profile_dialog QPushButton#TransportPrimary {
    background-color: #6335D9;
    color: #ffffff;
    border: 1px solid #7C3AED;
    border-radius: 5px;
    min-height: 26px;
    padding: 0 14px;
    font-weight: 600;
}

QDialog#profile_dialog QPushButton#SecondaryButton {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #23415E;
    border-radius: 5px;
    min-height: 26px;
    padding: 0 12px;
}
"""


def build_profile_page_qss() -> str:
    return studio_workspace_qss("profile_workspace") + PROFILE_EXTRAS
