"""Horizontal scroll chip pickers for Studio Expert controls (not Creator dropdowns)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)


def float_step_options(
    minimum: float,
    maximum: float,
    step: float,
    *,
    decimals: int = 2,
) -> tuple[tuple[str, str], ...]:
    """Build discrete chip options covering ``minimum..maximum`` inclusive."""
    if step <= 0:
        step = 0.05
    lo = float(minimum)
    hi = float(maximum)
    if hi < lo:
        lo, hi = hi, lo
    scale = 10**max(0, int(decimals))
    start = int(round(lo * scale))
    end = int(round(hi * scale))
    step_i = max(1, int(round(float(step) * scale)))
    rows: list[tuple[str, str]] = []
    value_i = start
    while value_i <= end:
        num = value_i / scale
        key = f"{num:.{decimals}f}"
        rows.append((key, key))
        value_i += step_i
    if not rows:
        key = f"{lo:.{decimals}f}"
        rows.append((key, key))
    # Ensure max is present (float drift).
    last_key = f"{hi:.{decimals}f}"
    if rows[-1][0] != last_key:
        rows.append((last_key, last_key))
    return tuple(rows)


class ScrollCatalogPicker(QWidget):
    """Exclusive horizontal chip strip for catalog / Expert numeric options."""

    selection_changed = Signal(str)
    float_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._order: list[str] = []
        self._value = "none"
        self._binding = False
        self._decimals = 2

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(44)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._host = QWidget()
        self._row = QHBoxLayout(self._host)
        self._row.setContentsMargins(0, 2, 0, 2)
        self._row.setSpacing(6)
        self._row.addStretch(1)
        self._scroll.setWidget(self._host)
        root.addWidget(self._scroll)

        self.setStyleSheet(
            """
            QPushButton#studioCatalogChip {
                min-height: 32px;
                max-height: 32px;
                padding: 0 12px;
                border-radius: 8px;
                border: 1px solid #2a3358;
                background: #0c1230;
                color: #c7d0ef;
                font-family: "Open Sans";
                font-size: 12px;
            }
            QPushButton#studioCatalogChip:hover {
                border-color: #7466F1;
                color: #ffffff;
            }
            QPushButton#studioCatalogChip:checked {
                border-color: #A259FF;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7466F1, stop:1 #A259FF);
                color: #ffffff;
            }
            """
        )

    def set_options(
        self,
        options: tuple[tuple[str, str], ...] | list[tuple[str, str]],
        *,
        include_none: bool = True,
        none_label: str = "None",
    ) -> None:
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons.clear()
        self._order.clear()

        rows: list[tuple[str, str]] = []
        if include_none:
            rows.append(("none", none_label))
        rows.extend((str(value), str(label)) for value, label in options)

        for value, label in rows:
            btn = QPushButton(label)
            btn.setObjectName("studioCatalogChip")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("catalogValue", value)
            btn.clicked.connect(lambda _checked=False, v=value: self._on_chip(v))
            self._row.addWidget(btn)
            self._buttons[value] = btn
            self._order.append(value)
        self._row.addStretch(1)

        if self._value not in self._buttons and self._order:
            self._value = self._order[0]
        self._sync_checked()

    def set_float_range(
        self,
        minimum: float,
        maximum: float,
        step: float,
        *,
        decimals: int = 2,
        value: float | None = None,
    ) -> None:
        self._decimals = int(decimals)
        opts = float_step_options(minimum, maximum, step, decimals=self._decimals)
        self.set_options(opts, include_none=False)
        if value is not None:
            self.set_float(value, fallback=float(minimum))

    def current_data(self) -> str:
        return self._value

    def current_float(self) -> float:
        try:
            return float(self._value)
        except (TypeError, ValueError):
            return 0.0

    def set_value(self, value: str | None, *, fallback: str = "none") -> None:
        target = str(value or fallback)
        if target not in self._buttons:
            target = fallback if fallback in self._buttons else (self._order[0] if self._order else "none")
        self._binding = True
        self._value = target
        self._sync_checked()
        self._ensure_visible(target)
        self._binding = False

    def set_float(self, value: float | None, *, fallback: float = 0.0) -> None:
        try:
            num = float(value) if value is not None else float(fallback)
        except (TypeError, ValueError):
            num = float(fallback)
        key = f"{num:.{self._decimals}f}"
        if key not in self._buttons:
            # Snap to nearest chip.
            best = None
            best_dist = None
            for option in self._order:
                try:
                    dist = abs(float(option) - num)
                except (TypeError, ValueError):
                    continue
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best = option
            key = best or f"{fallback:.{self._decimals}f}"
        self.set_value(key, fallback=key)

    def _on_chip(self, value: str) -> None:
        if value == self._value and self._buttons.get(value) and self._buttons[value].isChecked():
            self._sync_checked()
            return
        self._value = value
        self._sync_checked()
        self._ensure_visible(value)
        if not self._binding:
            self.selection_changed.emit(value)
            try:
                self.float_changed.emit(float(value))
            except (TypeError, ValueError):
                pass

    def _sync_checked(self) -> None:
        for key, btn in self._buttons.items():
            blocked = btn.blockSignals(True)
            btn.setChecked(key == self._value)
            btn.blockSignals(blocked)

    def _ensure_visible(self, value: str) -> None:
        btn = self._buttons.get(value)
        if btn is not None:
            self._scroll.ensureWidgetVisible(btn, 24, 0)
