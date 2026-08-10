"""Compact labeled horizontal sliders for Studio Tuning rows."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSlider, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class ExpertFloatSlider(QWidget):
    """Single-row ``Label (value)`` + track — compact Studio Tuning control."""

    float_changed = Signal(float)

    def __init__(
        self,
        label: str,
        *,
        minimum: float,
        maximum: float,
        step: float,
        decimals: int = 2,
        value: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label_text = str(label or "").strip() or "Value"
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        safe_step = float(step) if float(step) > 0 else 1.0
        self._step = safe_step
        self._decimals = max(0, int(decimals))
        self._steps = max(1, round((self._maximum - self._minimum) / safe_step))

        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._caption = QLabel()
        self._caption.setObjectName(SUBTITLE_LABEL_ID)
        self._caption.setFixedWidth(118)
        self._caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._steps)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(max(1, self._steps // 10))
        self._slider.setFixedHeight(16)
        self._slider.valueChanged.connect(self._on_slider)
        root.addWidget(self._caption)
        root.addWidget(self._slider, stretch=1)

        self.set_float(value, emit=False)

    def _format(self, raw: float) -> str:
        if self._decimals <= 0:
            return str(int(round(raw)))
        text = f"{raw:.{self._decimals}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _to_slider(self, raw: float) -> int:
        return int(round((_clamp(raw, self._minimum, self._maximum) - self._minimum) / self._step))

    def _from_slider(self, index: int) -> float:
        snapped = self._minimum + int(index) * self._step
        return round(_clamp(snapped, self._minimum, self._maximum), self._decimals)

    def _refresh_caption(self, raw: float) -> None:
        self._caption.setText(f"{self._label_text} ({self._format(raw)})")
        self._caption.setToolTip(self._caption.text())

    def _on_slider(self, index: int) -> None:
        value = self._from_slider(index)
        self._refresh_caption(value)
        self.float_changed.emit(value)

    def current_float(self) -> float:
        return self._from_slider(self._slider.value())

    def set_float(self, value: float, *, emit: bool = False) -> None:
        index = self._to_slider(float(value))
        blocked = self._slider.blockSignals(True)
        self._slider.setValue(index)
        self._slider.blockSignals(blocked)
        resolved = self._from_slider(self._slider.value())
        self._refresh_caption(resolved)
        if emit:
            self.float_changed.emit(resolved)

    def set_label(self, label: str) -> None:
        """Update the caption stem (value suffix stays current)."""
        self._label_text = str(label or "").strip() or "Value"
        self._refresh_caption(self.current_float())
