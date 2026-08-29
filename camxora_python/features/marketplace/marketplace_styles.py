"""Marketplace QSS — Create studio stylesheet plus Marketplace-only object names."""

from __future__ import annotations

from features.create.create_styles import studio_workspace_qss

MARKETPLACE_EXTRAS = """
QWidget#marketplace_workspace,
QWidget#marketplace_workspace QScrollArea,
QScrollArea#marketplace_workspace,
QScrollArea#marketplace_workspace > QWidget {
    background-color: #071426;
    border: none;
}

QWidget#marketplace_workspace QFrame#Panel,
QWidget#marketplace_workspace QFrame#CreateHeader,
QWidget#marketplace_workspace QFrame#NestedPanel {
    background-color: #0D1B2E;
    border: 1px solid #23415E;
    border-radius: 6px;
}

QWidget#marketplace_workspace QFrame#NestedPanel {
    background-color: #0A1628;
    border: 1px solid #18304A;
}

QWidget#marketplace_workspace QLabel#MarketplacePreview {
    background-color: #101F32;
    color: #8FA4BB;
    border: 1px solid #18304A;
    border-radius: 5px;
    font-size: 12px;
}

QWidget#marketplace_workspace QLabel#MarketplaceCardTitle {
    color: #E5EDF7;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

QWidget#marketplace_workspace QLabel#MarketplacePrice {
    color: #FBBF24;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

QWidget#marketplace_workspace QLabel#MarketplacePrice[tone="free"] {
    color: #22C55E;
}

QWidget#marketplace_workspace QLabel#MarketplaceKindBadge {
    color: #8FA4BB;
    font-size: 10px;
    font-weight: 600;
    border-radius: 3px;
    padding: 2px 8px;
    background-color: #23415E;
}

QWidget#marketplace_workspace QLabel#MarketplaceKindBadge[kind="video"] {
    background-color: #1E3A8A;
    color: #93C5FD;
}

QWidget#marketplace_workspace QLabel#MarketplaceKindBadge[kind="reel"] {
    background-color: #4C1D95;
    color: #DDD6FE;
}

QWidget#marketplace_workspace QPushButton#FilterChip {
    background-color: #101F32;
    color: #8FA4BB;
    border: 1px solid #18304A;
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 12px;
    min-height: 28px;
}

QWidget#marketplace_workspace QPushButton#FilterChip:hover {
    border-color: #23415E;
}

QWidget#marketplace_workspace QPushButton#FilterChip:checked {
    background-color: #6335D9;
    color: #ffffff;
    border-color: #6335D9;
}

QWidget#marketplace_workspace QLineEdit#MarketplaceSearch {
    background-color: #101F32;
    color: #E5EDF7;
    border: 1px solid #18304A;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 12px;
    min-height: 28px;
}

QWidget#marketplace_workspace QLineEdit#MarketplaceSearch:focus {
    border-color: #7466F1;
}

QWidget#marketplace_workspace QFrame#marketplace_error_banner {
    background-color: #2A1220;
    border: 1px solid #7F1D1D;
    border-radius: 6px;
}

QWidget#marketplace_workspace QLabel#marketplace_error_text {
    color: #FCA5A5;
    font-size: 12px;
    background: transparent;
}
"""


def build_marketplace_page_qss() -> str:
    return studio_workspace_qss("marketplace_workspace") + MARKETPLACE_EXTRAS
