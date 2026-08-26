"""Native Upgrade-required dialog — Music web Choose Your Plan UI."""

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
from shared.models.auth import WebMusicSubscriptionPlan
from shared.services.build_config import get_onboarding_url, get_pricing_url
from shared.services.platform_api import PlatformApi

FREE_DAILY_CREDITS = 50
FREE_FEATURES = ["Web Create", "Daily credit reset", "Top-up packs"]
DEFAULT_PAID_FEATURES = ["Web Create", "Desktop studio", "Dual channels", "Top-up packs"]
CREDITS_PER_SONG = 10


def format_subscription_price(cents: int) -> str:
    return f"${max(0, int(cents)) / 100.0:,.2f}"


def credits_to_songs(credits: int, credits_per_generate: float | int | None = None) -> int:
    per = float(credits_per_generate or CREDITS_PER_SONG)
    if per <= 0:
        per = float(CREDITS_PER_SONG)
    generates = int(max(0, int(credits)) / per)
    return generates * 2


def format_plan_display_name(plan_name: str) -> str:
    """Match music_web `formatPlanDisplayName`."""
    trimmed = plan_name.strip()
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


def calculate_yearly_discount(monthly_cents: int, yearly_cents: int) -> int:
    yearly_equiv = monthly_cents * 12
    if yearly_equiv <= 0:
        return 15
    return max(0, round(((yearly_equiv - yearly_cents) / yearly_equiv) * 100))


def plan_feature_lines(plan: WebMusicSubscriptionPlan) -> list[str]:
    features = [str(item).strip() for item in (plan.features or []) if str(item).strip()]
    return features or list(DEFAULT_PAID_FEATURES)


class UpgradePlansDialog(QDialog):
    """Native Music-style Choose Your Plan dialog after unpaid desktop login."""

    def __init__(
        self,
        *,
        message: str = "",
        api: PlatformApi | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upgrade required")
        self.setModal(True)
        self.setMinimumWidth(920)
        self.setMinimumHeight(560)
        self.resize(980, 600)
        self._api = api or PlatformApi()
        self._plans: list[WebMusicSubscriptionPlan] = []
        self._billing_cycle = "monthly"
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

        title = QLabel("Choose Your Plan")
        title.setObjectName("upgrade_hero_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Start creating amazing music with AI")
        subtitle.setObjectName("upgrade_hero_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        root.addWidget(self._build_billing_toggle(), alignment=Qt.AlignmentFlag.AlignCenter)

        self._status = QLabel("Loading plans…")
        self._status.setObjectName("upgrade_status")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

        # Fixed 4-up row (no vertical stack) — cards share width equally.
        self._cards_host = QWidget()
        self._cards_layout = QHBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(self._cards_host, stretch=1)

        footer = QLabel(
            "All paid plans include high-quality audio downloads and commercial usage rights."
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
        portal_btn = QPushButton("Open portal to upgrade")
        portal_btn.setObjectName("upgrade_primary_btn")
        portal_btn.clicked.connect(self._open_portal)
        actions.addWidget(portal_btn)
        root.addLayout(actions)

        self._load_plans()

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
            QFrame#upgrade_billing_toggle {
                background-color: rgba(255, 255, 255, 0.05);
                border-radius: 999px;
                padding: 2px;
            }
            QPushButton#upgrade_cycle_btn {
                background: transparent;
                border: none;
                color: #94a3b8;
                border-radius: 999px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
                min-height: 28px;
            }
            QPushButton#upgrade_cycle_btn[active="true"] {
                background-color: #7c3aed;
                color: #ffffff;
            }
            QLabel#upgrade_save_badge {
                color: #4ade80;
                background-color: rgba(74, 222, 128, 0.16);
                border-radius: 999px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 600;
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
            QPushButton#upgrade_plan_cta:disabled {
                color: rgba(255, 255, 255, 0.55);
                background-color: rgba(255, 255, 255, 0.08);
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
            QFrame#upgrade_icon_free {
                background-color: #475569;
                border-radius: 8px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
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

    def _build_billing_toggle(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("upgrade_billing_toggle")
        row = QHBoxLayout(frame)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(4)

        self._monthly_btn = QPushButton("Monthly")
        self._monthly_btn.setObjectName("upgrade_cycle_btn")
        self._monthly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._monthly_btn.clicked.connect(lambda: self._set_billing_cycle("monthly"))
        row.addWidget(self._monthly_btn)

        yearly_wrap = QHBoxLayout()
        yearly_wrap.setContentsMargins(0, 0, 0, 0)
        yearly_wrap.setSpacing(6)
        self._yearly_btn = QPushButton("Yearly")
        self._yearly_btn.setObjectName("upgrade_cycle_btn")
        self._yearly_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yearly_btn.clicked.connect(lambda: self._set_billing_cycle("yearly"))
        yearly_wrap.addWidget(self._yearly_btn)
        self._save_badge = QLabel("Save 15%")
        self._save_badge.setObjectName("upgrade_save_badge")
        yearly_wrap.addWidget(self._save_badge)
        row.addLayout(yearly_wrap)

        self._sync_cycle_buttons()
        return frame

    def _sync_cycle_buttons(self) -> None:
        self._monthly_btn.setProperty("active", "true" if self._billing_cycle == "monthly" else "false")
        self._yearly_btn.setProperty("active", "true" if self._billing_cycle == "yearly" else "false")
        for btn in (self._monthly_btn, self._yearly_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _set_billing_cycle(self, cycle: str) -> None:
        if cycle not in {"monthly", "yearly"} or cycle == self._billing_cycle:
            return
        self._billing_cycle = cycle
        self._sync_cycle_buttons()
        self._render_cards()

    def _load_plans(self) -> None:
        try:
            self._plans = self._api.list_web_music_subscription_plans()
        except Exception as exc:
            self._status.setText(
                f"Unable to load plans ({exc}). Open Music pricing or the account portal."
            )
            self._plans = []
            self._render_cards()
            return
        self._update_discount_badge()
        if not any(p.price_cents > 0 for p in self._plans):
            self._status.setText("No paid plans are published yet.")
        else:
            self._status.hide()
        self._render_cards()

    def _update_discount_badge(self) -> None:
        monthly = [p for p in self._plans if p.billing_cycle == "monthly" and p.price_cents > 0]
        yearly = [p for p in self._plans if p.billing_cycle == "yearly" and p.price_cents > 0]
        if monthly and yearly:
            pct = calculate_yearly_discount(monthly[0].price_cents, yearly[0].price_cents)
            self._save_badge.setText(f"Save {pct}%")
        else:
            self._save_badge.setText("Save 15%")

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_cards(self) -> None:
        self._clear_cards()
        cards: list[QFrame] = [self._free_card()]
        paid = [
            plan
            for plan in self._plans
            if plan.billing_cycle == self._billing_cycle and plan.price_cents > 0
        ]
        paid.sort(key=lambda item: (item.display_order, item.price_cents, item.name))
        cards.extend(self._paid_card(plan) for plan in paid)
        for card in cards:
            self._cards_layout.addWidget(card, stretch=1)

    def _icon_badge(self, *, paid: bool, glyph: str) -> QFrame:
        badge = QFrame()
        badge.setObjectName("upgrade_icon_paid" if paid else "upgrade_icon_free")
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

    def _free_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("upgrade_plan_card")
        card.setMinimumWidth(160)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._icon_badge(paid=False, glyph="🎁"))
        name = QLabel("Free")
        name.setObjectName("upgrade_plan_name")
        header.addWidget(name, stretch=1)
        layout.addLayout(header)

        price_row = QHBoxLayout()
        price_row.setSpacing(4)
        price = QLabel("$0")
        price.setObjectName("upgrade_plan_price")
        price_row.addWidget(price)
        suffix = QLabel("/mo")
        suffix.setObjectName("upgrade_plan_price_suffix")
        price_row.addWidget(suffix)
        price_row.addStretch(1)
        layout.addLayout(price_row)

        credits = QFrame()
        credits.setObjectName("upgrade_credits_box")
        credits_layout = QVBoxLayout(credits)
        credits_layout.setContentsMargins(8, 8, 8, 8)
        credits_layout.setSpacing(1)
        credits_label = QLabel("Daily Credits")
        credits_label.setObjectName("upgrade_credits_label")
        credits_layout.addWidget(credits_label)
        credits_value = QLabel(str(FREE_DAILY_CREDITS))
        credits_value.setObjectName("upgrade_credits_value")
        credits_layout.addWidget(credits_value)
        credits_hint = QLabel("Credit reset daily")
        credits_hint.setObjectName("upgrade_credits_hint")
        credits_layout.addWidget(credits_hint)
        layout.addWidget(credits)

        for feature in FREE_FEATURES:
            layout.addWidget(self._feature_row(feature))
        layout.addStretch(1)

        cta = QPushButton("Current plan")
        cta.setObjectName("upgrade_plan_cta")
        cta.setEnabled(False)
        layout.addWidget(cta)
        return card

    def _paid_card(self, plan: WebMusicSubscriptionPlan) -> QFrame:
        display_name = format_plan_display_name(plan.name)
        songs = credits_to_songs(plan.monthly_credits, plan.credits_per_generate)
        cycle_suffix = "/mo" if self._billing_cycle == "monthly" else "/yr"

        card = QFrame()
        card.setObjectName("upgrade_plan_card")
        card.setMinimumWidth(160)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(self._icon_badge(paid=True, glyph="✦"))
        name = QLabel(display_name)
        name.setObjectName("upgrade_plan_name")
        name.setWordWrap(True)
        header.addWidget(name, stretch=1)
        layout.addLayout(header)

        price_row = QHBoxLayout()
        price_row.setSpacing(4)
        price = QLabel(format_subscription_price(plan.price_cents))
        price.setObjectName("upgrade_plan_price")
        price_row.addWidget(price)
        suffix = QLabel(cycle_suffix)
        suffix.setObjectName("upgrade_plan_price_suffix")
        price_row.addWidget(suffix)
        price_row.addStretch(1)
        layout.addLayout(price_row)

        credits = QFrame()
        credits.setObjectName("upgrade_credits_box")
        credits_layout = QVBoxLayout(credits)
        credits_layout.setContentsMargins(8, 8, 8, 8)
        credits_layout.setSpacing(1)
        credits_label = QLabel("Monthly Credits")
        credits_label.setObjectName("upgrade_credits_label")
        credits_layout.addWidget(credits_label)
        credits_value = QLabel(f"{int(plan.monthly_credits):,}")
        credits_value.setObjectName("upgrade_credits_value")
        credits_layout.addWidget(credits_value)
        credits_hint = QLabel(f"~ {songs:,} songs/mo")
        credits_hint.setObjectName("upgrade_credits_hint")
        credits_layout.addWidget(credits_hint)
        layout.addWidget(credits)

        for feature in plan_feature_lines(plan):
            layout.addWidget(self._feature_row(feature))
        layout.addStretch(1)

        cta = QPushButton(f"Get {display_name}")
        cta.setObjectName("upgrade_plan_cta")
        cta.setCursor(Qt.CursorShape.PointingHandCursor)
        cta.clicked.connect(self._open_music_pricing)
        layout.addWidget(cta)
        return card

    def _open_music_pricing(self) -> None:
        QDesktopServices.openUrl(QUrl(get_pricing_url(embed=False)))

    def _open_portal(self) -> None:
        QDesktopServices.openUrl(QUrl(get_onboarding_url()))
        self.accept()
