"""Typography label components for the design system.

Provides TypedLabel — a QLabel subclass that maps typography levels to
Qt dynamic property values for QSS styling.
"""

import logging

from PyQt6.QtWidgets import QLabel, QWidget

logger = logging.getLogger(__name__)


class TypedLabel(QLabel):
    """A QLabel that applies a typography level via the uiRole dynamic property.

    The level controls font size, weight, and color through QSS property selectors
    (e.g. QLabel[uiRole="page_title"]). Calling setText() updates the displayed
    text without altering the assigned level/role.

    Supported levels: page_title, section_title, subtitle, body, caption, muted.
    """

    LEVELS: tuple[str, ...] = (
        "page_title",
        "section_title",
        "subtitle",
        "body",
        "caption",
        "muted",
    )

    def __init__(
        self, text: str, level: str = "body", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self.setLevel(level)

    def setLevel(self, level: str) -> None:
        """Set the typography level, updating the uiRole property for QSS.

        If *level* is not recognized, falls back to "body" with a warning.
        """
        if level not in self.LEVELS:
            logger.warning(
                "Unknown typography level '%s'; falling back to 'body'. "
                "Valid levels: %s",
                level,
                ", ".join(self.LEVELS),
            )
            level = "body"

        self.setProperty("uiRole", level)
        # Force QSS re-evaluation so the new property value takes effect
        self.style().unpolish(self)
        self.style().polish(self)
