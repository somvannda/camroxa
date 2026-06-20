"""Legacy theme module — DEPRECATED.

All style generation is now handled by the unified design system pipeline:
    ThemeTokens → QSSGenerator → QApplication.setStyleSheet()

These functions are retained only for backward compatibility and will emit
DeprecationWarning when called.
"""

from __future__ import annotations

import warnings


def build_ui_tokens() -> dict[str, str]:
    """Return a flat token dictionary for legacy callers.

    .. deprecated::
        Use ``TokenRegistry.as_dict()`` from ``python_app.design_system.tokens`` instead.
    """
    warnings.warn(
        "build_ui_tokens() is deprecated. Use TokenRegistry.as_dict() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from python_app.design_system.tokens import TokenRegistry

    return TokenRegistry().as_dict()  # type: ignore[return-value]


def build_app_stylesheet(*args, **kwargs) -> str:  # noqa: ANN002, ANN003
    """No-op stylesheet builder for legacy callers.

    .. deprecated::
        Use ``design_system.bootstrap.apply_theme()`` instead.
    """
    warnings.warn(
        "build_app_stylesheet() is deprecated. Use design_system.bootstrap.apply_theme() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return ""
