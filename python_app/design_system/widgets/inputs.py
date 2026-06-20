"""Styled input field components for the design system.

Provides StyledLineEdit, StyledComboBox, and StyledSpinBox with field_variant
property support for QSS property-selector matching.
"""

import logging

from PyQt6.QtWidgets import QLineEdit, QComboBox, QSpinBox

logger = logging.getLogger(__name__)

_VALID_FIELD_VARIANTS = ("card", "standalone")


def _validate_field_variant(variant: str) -> str:
    """Validate field variant, falling back to 'standalone' with warning if invalid."""
    if variant in _VALID_FIELD_VARIANTS:
        return variant
    logger.warning(
        "Invalid field_variant '%s'. Expected one of %s. Falling back to 'standalone'.",
        variant,
        _VALID_FIELD_VARIANTS,
    )
    return "standalone"


class StyledLineEdit(QLineEdit):
    """A styled text input with field_variant property for QSS matching.

    Supports "card" variant (transparent background for card containers) and
    "standalone" variant (solid dark background for page surfaces).
    """

    def __init__(
        self,
        field_variant: str = "standalone",
        placeholder: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        variant = _validate_field_variant(field_variant)
        self.setProperty("uiField", variant)
        if placeholder:
            self.setPlaceholderText(placeholder)


class StyledComboBox(QComboBox):
    """A styled combo box with field_variant property for QSS matching.

    Supports "card" variant (transparent background for card containers) and
    "standalone" variant (solid dark background for page surfaces).
    """

    def __init__(
        self,
        field_variant: str = "standalone",
        parent=None,
    ) -> None:
        super().__init__(parent)
        variant = _validate_field_variant(field_variant)
        self.setProperty("uiField", variant)


class StyledSpinBox(QSpinBox):
    """A styled spin box with field_variant property for QSS matching.

    Supports "card" variant (transparent background for card containers) and
    "standalone" variant (solid dark background for page surfaces).
    """

    def __init__(
        self,
        field_variant: str = "standalone",
        parent=None,
    ) -> None:
        super().__init__(parent)
        variant = _validate_field_variant(field_variant)
        self.setProperty("uiField", variant)
