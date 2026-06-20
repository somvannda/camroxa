"""Transport control widgets for audio playback.

Provides TransportButton (circular icon button for play/pause/skip) and
SeekBar (slider with elapsed/total time labels) for the audio player section.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from python_app.design_system.widgets.custom_slider import CustomSlider
from python_app.design_system.widgets.labels import TypedLabel


class TransportButton(QPushButton):
    """Circular transport button with an SVG icon.

    Applies the "transport" or "transportPrimary" uiRole for QSS styling and
    sets a fixed size based on the chosen size variant.

    Attributes:
        SIZES: Mapping from size variant name to pixel dimension.
    """

    SIZES: dict[str, int] = {"small": 28, "medium": 36, "large": 44}

    def __init__(
        self,
        icon_name: str,
        size: str = "medium",
        variant: str = "default",
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Resolve pixel size
        px = self.SIZES.get(size, self.SIZES["medium"])
        self.setFixedSize(px, px)

        # Apply uiRole for QSS property-selector styling
        if variant == "primary":
            self.setProperty("uiRole", "transportPrimary")
        else:
            self.setProperty("uiRole", "transport")

        # Make button circular via border-radius inline style
        radius = px // 2
        self.setStyleSheet(f"border-radius: {radius}px;")

        # Icon
        if icon_name:
            icon = QIcon(icon_name)
            self.setIcon(icon)
            icon_size = int(px * 0.5)
            self.setIconSize(QSize(icon_size, icon_size))

        # Tooltip
        if tooltip:
            self.setToolTip(tooltip)


def _format_time(ms: int) -> str:
    """Format milliseconds as MM:SS string."""
    if ms < 0:
        ms = 0
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


class SeekBar(QWidget):
    """Audio seek bar composing a slider with elapsed/total time labels.

    Emits valueChanged(int) when the slider position changes. Time labels
    display elapsed and total duration formatted as "MM:SS".
    """

    valueChanged = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Elapsed time label
        self._elapsed_label = TypedLabel("00:00", level="caption")
        self._elapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Internal slider (min=0, max=1000 for millisecond granularity)
        self._slider = CustomSlider(
            orientation=Qt.Orientation.Horizontal,
            minimum=0,
            maximum=1000,
            step=1,
        )

        # Total duration label
        self._total_label = TypedLabel("00:00", level="caption")
        self._total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._elapsed_label)
        layout.addWidget(self._slider, 1)  # slider takes available space
        layout.addWidget(self._total_label)

        # Connect internal slider signal
        self._slider.valueChanged.connect(self._on_slider_changed)

    def _on_slider_changed(self, value: int) -> None:
        """Handle internal slider value change."""
        self._elapsed_label.setText(_format_time(value))
        self.valueChanged.emit(value)

    def setRange(self, minimum: int, maximum: int) -> None:
        """Set the slider range."""
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)

    def setValue(self, value: int) -> None:
        """Set the slider value and update the elapsed label."""
        self._slider.setValue(value)
        self._elapsed_label.setText(_format_time(value))

    def setDuration(self, total_ms: int) -> None:
        """Set total duration, updating the total label and slider maximum."""
        self._total_label.setText(_format_time(total_ms))
        self._slider.setMaximum(total_ms)
