"""Custom slider widget component.

Provides a styled QSlider with configurable min, max, step, and orientation.
Styling is handled via the global QSS (QSlider::groove, ::handle, ::sub-page
selectors from the QSS generator). The widget validates construction parameters
and configures QSlider accordingly.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSlider, QWidget


class CustomSlider(QSlider):
    """Styled slider with configurable range, step, and orientation.

    The slider is styled via the application-wide QSS produced by QSSGenerator.
    It provides a muted track background, accent-colored sub-page fill, and a
    styled handle with border. Both horizontal and vertical orientations are
    supported.

    Signals:
        valueChanged(int): Emitted when the slider value changes (inherited from QSlider).

    Raises:
        ValueError: If minimum >= maximum at construction time.
    """

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        minimum: int = 0,
        maximum: int = 100,
        step: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        if minimum >= maximum:
            raise ValueError(
                f"Slider minimum ({minimum}) must be less than maximum ({maximum})."
            )

        super().__init__(orientation, parent)

        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setSingleStep(step)
        self.setPageStep(step * 10 if step * 10 <= (maximum - minimum) else step)
