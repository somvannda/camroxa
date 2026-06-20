"""Backward-compatibility shims for the design system.

Provides utilities that help track inline stylesheet conflicts during
incremental migration from manual styling to design system components.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QWidget

logger = logging.getLogger("design_system.compat")


def check_inline_stylesheet_conflict(widget: QWidget, role_name: str) -> None:
    """Log deprecation warning if widget has both inline stylesheet and a design system role.

    This function should be called when assigning a design system Style_Role
    to a widget. If the widget already has an inline stylesheet set, a warning
    is logged to help developers track widgets that need migration.

    Args:
        widget: The QWidget being assigned a design system role.
        role_name: The Style_Role name being applied (e.g. "primary", "danger").
    """
    if widget.styleSheet().strip():
        identifier = widget.objectName() or widget.__class__.__name__
        logger.warning(
            "Widget '%s' has both inline stylesheet and design system role '%s'. "
            "Consider removing the inline stylesheet for full design system control.",
            identifier,
            role_name,
        )
