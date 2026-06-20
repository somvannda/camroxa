"""Coordinate mapper for converting between widget pixels, canvas percentages, and output pixels.

Handles aspect ratio differences (letterboxing/pillarboxing) between the widget display
and the target output resolution, ensuring text positions are resolution-independent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CanvasRect:
    """The actual content area within the widget (accounting for aspect ratio letterboxing)."""

    x: int  # offset from widget left edge
    y: int  # offset from widget top edge
    width: int
    height: int


class CanvasCoordinateMapper:
    """Converts between widget pixels, canvas percentages (0-100), and output pixels.

    The mapper computes a content rect within the widget that preserves the target
    aspect ratio. All coordinate conversions map through this content rect rather
    than the full widget area, ensuring consistent text placement regardless of the
    preview widget's pixel dimensions.
    """

    def __init__(
        self,
        widget_width: int,
        widget_height: int,
        target_width: int,
        target_height: int,
    ):
        self._widget_w = widget_width
        self._widget_h = widget_height
        self._target_w = target_width
        self._target_h = target_height
        self._canvas_rect = self._compute_canvas_rect()

    def _compute_canvas_rect(self) -> CanvasRect:
        """Compute the content area within the widget that maps to the target resolution,
        accounting for aspect ratio differences (letterboxing/pillarboxing).

        Uses a fit-inside approach: the largest rectangle with the target aspect ratio
        that fits within the widget dimensions, centered within the widget.
        """
        if self._widget_w <= 0 or self._widget_h <= 0:
            return CanvasRect(x=0, y=0, width=0, height=0)

        if self._target_w <= 0 or self._target_h <= 0:
            return CanvasRect(x=0, y=0, width=self._widget_w, height=self._widget_h)

        target_aspect = self._target_w / self._target_h
        widget_aspect = self._widget_w / self._widget_h

        if widget_aspect > target_aspect:
            # Widget is wider than target — pillarboxing (black bars on sides)
            canvas_height = self._widget_h
            canvas_width = int(round(canvas_height * target_aspect))
        else:
            # Widget is taller than target — letterboxing (black bars top/bottom)
            canvas_width = self._widget_w
            canvas_height = int(round(canvas_width / target_aspect))

        # Center the content rect within the widget
        x = (self._widget_w - canvas_width) // 2
        y = (self._widget_h - canvas_height) // 2

        return CanvasRect(x=x, y=y, width=canvas_width, height=canvas_height)

    def widget_to_pct(self, widget_x: int, widget_y: int) -> tuple[float, float]:
        """Convert widget pixel position to canvas percentage (0-100).
        Accounts for aspect ratio offset (letterboxing/pillarboxing).

        Returns (pct_x, pct_y) where values can be outside 0-100 if the position
        is outside the content rect.
        """
        rect = self._canvas_rect
        if rect.width <= 0 or rect.height <= 0:
            return (0.0, 0.0)

        # Subtract the offset to get position relative to content rect
        rel_x = widget_x - rect.x
        rel_y = widget_y - rect.y

        pct_x = (rel_x / rect.width) * 100.0
        pct_y = (rel_y / rect.height) * 100.0

        return (pct_x, pct_y)

    def pct_to_widget(self, pct_x: float, pct_y: float) -> tuple[int, int]:
        """Convert canvas percentage to widget pixel position."""
        rect = self._canvas_rect

        widget_x = int(round(rect.x + (pct_x / 100.0) * rect.width))
        widget_y = int(round(rect.y + (pct_y / 100.0) * rect.height))

        return (widget_x, widget_y)

    def pct_to_output(self, pct_x: float, pct_y: float) -> tuple[int, int]:
        """Convert canvas percentage to output resolution pixel position."""
        if self._target_w <= 0 or self._target_h <= 0:
            return (0, 0)

        output_x = int(round((pct_x / 100.0) * self._target_w))
        output_y = int(round((pct_y / 100.0) * self._target_h))

        return (output_x, output_y)

    def output_to_pct(self, output_x: int, output_y: int) -> tuple[float, float]:
        """Convert output pixel position to canvas percentage."""
        if self._target_w <= 0 or self._target_h <= 0:
            return (0.0, 0.0)

        pct_x = (output_x / self._target_w) * 100.0
        pct_y = (output_y / self._target_h) * 100.0

        return (pct_x, pct_y)

    def widget_delta_to_pct_delta(self, dx: int, dy: int) -> tuple[float, float]:
        """Convert a widget-space pixel delta to a percentage delta.

        This converts movement in widget pixels to the equivalent movement
        in canvas percentage units.
        """
        rect = self._canvas_rect
        if rect.width <= 0 or rect.height <= 0:
            return (0.0, 0.0)

        dpct_x = (dx / rect.width) * 100.0
        dpct_y = (dy / rect.height) * 100.0

        return (dpct_x, dpct_y)

    @property
    def canvas_rect(self) -> CanvasRect:
        """The content area within the widget."""
        return self._canvas_rect

    def update(
        self,
        widget_width: int,
        widget_height: int,
        target_width: int,
        target_height: int,
    ) -> None:
        """Recalculate on resize or resolution change.

        Call this whenever the widget dimensions change (resize event) or when
        the target output resolution changes (resolution dropdown).
        """
        self._widget_w = widget_width
        self._widget_h = widget_height
        self._target_w = target_width
        self._target_h = target_height
        self._canvas_rect = self._compute_canvas_rect()
