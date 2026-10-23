"""Native credits-required dialog - web-music credit packs (packs-only billing).

The desktop studio is gated on live credit-pack credits. Subscriptions are no
longer sold, so this dialog mirrors the music.camxora.com "Buy Credits" modal:
one-time packs, valid for 30 days from purchase.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shared.lib.desktop_entitlement import DESKTOP_REQUIRES_PAID_PLAN_MESSAGE
from shared.models.auth import CreditPack
from shared.services.build_config import get_pricing_url
from shared.services.platform_api import PlatformApi

CREDITS_PER_SONG = 10
PACK_VALIDITY_DAYS = 30
PACK_FEATURES = [
    f"Valid for {PACK_VALIDITY_DAYS} days from purchase",
    "Buy again any time",
    "Instant delivery",
]


def format_subscription_price(cents: int) -> str:
    return f"${max(0, int(cents)) / 100.0:,.2f}"


def credits_to_songs(credits: int, credits_per_generate: float | int | None = None) -> int:
    per = float(credits_per_generate or CREDITS_PER_SONG)
    if per <= 0:
        per = float(CREDITS_PER_SONG)
    generates = int(max(0, int(credits)) / per)
    return generates * 2


def format_plan_display_name(plan_name: str) -> str:
    """Match music_web `formatPlanDisplayName` for legacy plan labels."""
    trimmed = str(plan_name or "").strip()
    pretty = re.search(r"\((monthly|yearly)\)$", trimmed, flags=re.IGNORECASE)
    slug = re.search(r"[-_\s]+(monthly|yearly)$", trimmed, flags=re.IGNORECASE)
    cycle = ((pretty.group(1) if pretty else None) or (slug.group(1) if slug else "")).lower()
    raw = re.sub(r"\s*\((monthly|yearly)\)$", "", trimmed, flags=re.IGNORECASE)
    raw = re.sub(r"[-_\s]+(monthly|yearly)$", "", raw, flags=re.IGNORECASE)
    raw = raw.replace("_", " ").strip()
    title = " ".join(part[:1].upper() + part[1:].lower() for part in raw.split() if part)
    label = title or "Plan"
    if cycle == "monthly":
        return f"{label} (Monthly)"
    if cycle == "yearly":
        return f"{label} (Yearly)"
    return label


def pack_feature_lines(pack: CreditPack) -> list[str]:
    lines = [line.strip() for line in str(pack.description or "").splitlines() if line.strip()]
    return lines or list(PACK_FEATURES)


class UpgradePlansDialog(QDialog):
    """Native Music-style "Buy Credits" dialog after an unpaid desktop login."""

    def __init__(
        self,
        *,
        message: str = "",
        api: PlatformApi | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Credits required")
        self.setModal(True)
        self.setMinimumWidth(920)
        self.setMinimumHeight(520)
        self.resize(980, 560)
        self._api = api or PlatformApi()
        self._packs: list[CreditPack] = []
        self._message = (message or DESKTOP_REQUIRES_PAID_PLAN_MESSAGE).strip()

        self.setObjectName("upgrade_plans_dialog")
        self.setStyleSheet(self._dialog_qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        gate = QLabel(self._message)
        gate.setObjectName("upgrade_gate_message")
        gate.setWordWrap(True)
        gate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(gate)

        title = QLabel("Buy Credits")
        title.setObjectName("upgrade_hero_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel(
            f"One-time purchase - credits valid for {PACK_VALIDITY_DAYS} days"
        )
        subtitle.setObjectName("upgrade_hero_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        self._status = QLabel("Loading credit packs...")
        self._status.setObjectName("upgrade_status")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

        # Fixed 4-up row (no vertical stack) - cards share width equally.
        self._cards_host = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._cards_host, stretch=1)

        footer = QLabel(
            f"Credits are valid for {PACK_VALIDITY_DAYS} days from purchase. "
            "Buying another pack resets the 30-day clock."
        )
        footer.setObjectName("upgrade_footer")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(footer)

        actions = QHBoxLayout()
        actions.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("upgrade_secondary_btn")
        close_btn.clicked.connect(self.reject)
        actions.addWidget(close_btn)
        browser_btn = QPushButton("Open Music pricing")
        browser_btn.setObjectName("upgrade_secondary_btn")
        browser_btn.clicked.connect(self._open_music_pricing)
        actions.addWidget(browser_btn)
        buy_btn = QPushButton("Buy credits on Music")
        buy_btn.setObjectName("upgrade_primary_btn")
        buy_btn.clicked.connect(self._open_music_pricing)
        actions.addWidget(buy_btn)
        root.addLayout(actions)

        self._load_packs()

    def _dialog_qss(self) -> str:
        return """
            QDialog#upgrade_plans_dialog {
                background-color: #0b1220;
            }
            QLabel#upgrade_gate_message {
                color: #94a3b8;
                font-size: 11px;
            }
            QLabel#upgrade_hero_title {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#upgrade_hero_subtitle {
                color: #94a3b8;
                font-size: 12px;
            }
            QLabel#upgrade_status, QLabel#upgrade_footer {
                color: #94a3b8;
                font-size: 11px;
            }
            QFrame#upgrade_plan_card {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
            }
            QLabel#upgrade_plan_name {
                color: #ffffff;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#upgrade_plan_price {
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#upgrade_plan_price_suffix {
                color: #94a3b8;
                font-size: 12px;
            }
            QFrame#upgrade_credits_box {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            }
            QLabel#upgrade_credits_label {
                color: #94a3b8;
                font-size: 11px;
            }
            QLabel#upgrade_credits_value {
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#upgrade_credits_hint {
                color: #64748b;
                font-size: 10px;
            }
            QLabel#upgrade_feature {
                color: #cbd5e1;
                font-size: 11px;
            }
            QLabel#upgrade_check {
                color: #4ade80;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#upgrade_plan_cta {
                background-color: rgba(255, 255, 255, 0.10);
                border: none;
                border-radius: 10px;
                color: #ffffff;
                font-size: 11px;
                font-weight: 600;
                min-height: 36px;
                padding: 6px 8px;
            }
            QPushButton#upgrade_plan_cta:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
            QPushButton#upgrade_secondary_btn {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                color: #ffffff;
                min-height: 36px;
                padding: 6px 12px;
            }
            QPushButton#upgrade_primary_btn {
                background-color: #16a34a;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-weight: 600;
                min-height: 36px;
                padding: 6px 12px;
            }
            QFrame#upgrade_icon_paid {
                background-color: #a855f7;
                border-radius: 8px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
            }
            QLabel#upgrade_icon_glyph {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
            }
        """

    def _load_packs(self) -> None:
        try:
            self._packs = self._api.list_credit_packs()
        except Exception as exc:
            self._status.setText(
                f"Unable to load credit packs ({exc}). Open Music pricing to buy credits."
            )
            self._packs = []
            self._render_cards()
            return
        if not self._packs:
            self._status.setText("No credit packs are published yet.")
        else:
            self._status.hide()
        self._render_cards()

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_cards(self) -> None:
        self._clear_cards()
        for pack in self._packs:
            self._cards_layout.addWidget(self._pack_card(pack), stretch=1)

    def _icon_badge(self, glyph: str) -> QFrame:
        badge = QFrame()
        badge.setObjectName("upgrade_icon_paid")
        layout = QVBoxLayout(badge)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(glyph)
        label.setObjectName("upgrade_icon_glyph")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return badge

    def _feature_row(self, text: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        check = QLabel("✓")
        check.setObjectName("upgrade_check")
        layout.addWidget(check, alignment=Qt.AlignmentFlag.AlignTop)
        label = QLabel(text)
        label.setObjectName("upgrade_feature")
        label.setWordWrap(True)
        layout.addWidget(label, stretch=1)
        return row

    def _pack_card(self, pack: CreditPack) -> QFrame:
        songs = credits_to_songs(pack.total_credits, CREDITS_PER_SONG)

        card = QFrame()
        card.setObjectName("upgrade_plan_card")
        card.setMinimumWidth(160)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._icon_badge("✦"))
        name = QLabel(pack.name)
        name.setObjectName("upgrade_plan_name")
        name.setWordWrap(True)
        header.addWidget(name, stretch=1)
        layout.addLayout(header)

        price_row = QHBoxLayout()
        price_row.setSpacing(4)
        price = QLabel(format_subscription_price(pack.price_cents))
        price.setObjectName("upgrade_plan_price")
        price_row.addWidget(price)
        suffix = QLabel("one-time")
        suffix.setObjectName("upgrade_plan_price_suffix")
        price_row.addWidget(suffix)
        price_row.addStretch(1)
        layout.addLayout(price_row)

        credits = QFrame()
        credits.setObjectName("upgrade_credits_box")
        credits_layout = QVBoxLayout(credits)
        credits_layout.setContentsMargins(8, 8, 8, 8)
        credits_layout.setSpacing(1)
        credits_label = QLabel("Credits")
        credits_label.setObjectName("upgrade_credits_label")
        credits_layout.addWidget(credits_label)
        credits_value = QLabel(f"{int(pack.total_credits):,}")
        credits_value.setObjectName("upgrade_credits_value")
        credits_layout.addWidget(credits_value)
        credits_hint = QLabel(f"~ {songs:,} songs")
        credits_hint.setObjectName("upgrade_credits_hint")
        credits_layout.addWidget(credits_hint)
        layout.addWidget(credits)

        for feature in pack_feature_lines(pack):
            layout.addWidget(self._feature_row(feature))
        layout.addStretch(1)

        cta = QPushButton(f"Buy {pack.name}")
        cta.setObjectName("upgrade_plan_cta")
        cta.setCursor(Qt.CursorShape.PointingHandCursor)
        cta.clicked.connect(self._open_music_pricing)
        layout.addWidget(cta)
        return card

    def _open_music_pricing(self) -> None:
        QDesktopServices.openUrl(QUrl(get_pricing_url(embed=False)))
