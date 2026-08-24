"""Credits card for the dashboard (one wallet number, no plan meters)."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from shared.lib.formatting import format_compact_number
from shared.models.platform import DashboardOverview
from shared.themes.deep_blue import SUBTITLE_LABEL_ID


class RemainingMonthCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        title = QLabel("CREDITS")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        hint = QLabel("One wallet number. Generate still works the same; leftover package counts are not shown as a plan.")
        hint.setObjectName(SUBTITLE_LABEL_ID)
        hint.setWordWrap(True)
        root.addWidget(hint)

        summary = QFrame()
        summary.setObjectName("dashboard_quota_summary")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(4)
        self._wallet = _SummaryLine("Credits balance", "--")
        self._spent = _SummaryLine("Spent this month", "--")
        summary_layout.addWidget(self._wallet)
        summary_layout.addWidget(self._spent)
        root.addWidget(summary)
        root.addStretch()

    def apply_overview(self, data: DashboardOverview) -> None:
        license_info = data.license
        wallet = (
            license_info.wallet_balance
            if license_info and license_info.wallet_balance is not None
            else data.me.credit_balance
        )
        self._wallet.set_value(format_compact_number(wallet))
        self._spent.set_value(format_compact_number(data.stats.credits_spent))


class _SummaryLine(QFrame):
    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setObjectName(SUBTITLE_LABEL_ID)
        self._value = QLabel(value)
        layout.addWidget(self._label)
        layout.addStretch()
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
