"""Login-page QSS scoped under #auth_page so other shells stay unchanged."""

AUTH_PAGE_QSS = """
QFrame#auth_page,
QWidget#auth_stage,
QFrame#auth_login_card,
QFrame#auth_login_card QLabel,
QFrame#auth_login_card QLineEdit,
QFrame#auth_login_card QPushButton,
QFrame#auth_login_card QCheckBox,
QFrame#auth_login_card QToolButton {
    font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
}

QFrame#auth_page {
    background-color: #020817;
}

QWidget#auth_stage {
    background-color: #020817;
}

QWidget#auth_waveform {
    background: transparent;
}

QFrame#auth_login_card {
    background-color: #0C1230;
    border: 1px solid #6845C7;
    border-radius: 14px;
}

QFrame#auth_login_card QLabel,
QFrame#auth_login_card QWidget {
    background: transparent;
}

QLabel#auth_brand_title {
    color: #F1F5F9;
    font-size: 15px;
    font-weight: 700;
}

QLabel#auth_brand_subtitle {
    color: #65748F;
    font-size: 9px;
    font-weight: 500;
}

QLabel#auth_welcome {
    background: transparent;
}

QLabel#auth_card_subtitle {
    color: #A7B4CC;
    font-size: 14px;
    font-weight: 400;
}

QLabel#auth_field_label {
    color: #A7B4CC;
    font-size: 12px;
    font-weight: 500;
}

QLineEdit#auth_input {
    background-color: #101B31;
    border: 1px solid #29466C;
    border-radius: 6px;
    color: #E5EDF7;
    padding: 0 40px 0 8px;
    min-height: 48px;
    max-height: 48px;
    font-size: 14px;
    selection-background-color: #6D3DF5;
}

QLineEdit#auth_input:focus {
    border-color: #8B5CF6;
}

QToolButton#auth_eye_button {
    background: transparent;
    border: none;
    padding: 0;
}

QCheckBox#auth_remember {
    color: #A7B4CC;
    font-size: 13px;
    spacing: 8px;
    background: transparent;
}

QCheckBox#auth_remember::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #29466C;
    background-color: #101B31;
}

QCheckBox#auth_remember::indicator:checked {
    background-color: #38BDF8;
    border-color: #38BDF8;
}

QPushButton#auth_forgot_button,
QPushButton#auth_switch_button {
    background: transparent;
    border: none;
    color: #8B5CF6;
    font-size: 13px;
    font-weight: 500;
    padding: 0;
}

QPushButton#auth_forgot_button:hover,
QPushButton#auth_switch_button:hover {
    color: #A78BFA;
}

QLabel#auth_section_label {
    color: #65748F;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.1px;
}

QFrame#auth_recent_card {
    background-color: #0A1026;
    border: 1px solid #24375A;
    border-radius: 8px;
}

QFrame#auth_recent_card:hover {
    background-color: #101B31;
    border-color: #6D3DF5;
}

QLabel#auth_recent_name {
    color: #F1F5F9;
    font-size: 13px;
    font-weight: 600;
}

QLabel#auth_recent_email {
    color: #65748F;
    font-size: 11px;
}

QToolButton#auth_recent_remove {
    background: transparent;
    border: none;
    padding: 2px;
}

QToolButton#auth_recent_remove:hover {
    background: rgba(239, 68, 68, 0.16);
    border-radius: 4px;
}

QPushButton#login_primary_button {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #6D3DF5,
        stop: 1 #9B4DFF
    );
    color: #ffffff;
    font-size: 15px;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    min-height: 48px;
    max-height: 48px;
    padding: 0 16px;
}

QPushButton#login_primary_button:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #7C4DFF,
        stop: 1 #B06AFF
    );
}

QPushButton#login_primary_button:pressed {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #5B21B6,
        stop: 1 #7E22CE
    );
}

QPushButton#login_primary_button:disabled {
    background-color: #3B2A6A;
    color: #A7B4CC;
}

QLabel#auth_error {
    color: #FCA5A5;
    font-size: 12px;
}

QLabel#auth_loading {
    color: #A7B4CC;
    font-size: 12px;
}
"""
