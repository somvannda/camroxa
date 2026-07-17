"""Template badge utilities — visual distinction for marketplace vs user/builtin templates.

Provides badge text, styling information, and delete-confirmation logic
based on the template source field.
"""

from __future__ import annotations


def get_template_badge_text(source: str) -> str | None:
    """Return badge text based on the template source.

    Args:
        source: The template source field ('marketplace', 'builtin', or 'user').

    Returns:
        Badge label string for marketplace/builtin templates, or None for user
        templates (no badge needed since user-created is the default).
    """
    normalized = source.strip().lower()
    if normalized == "marketplace":
        return "Marketplace"
    if normalized == "builtin":
        return "Built-in"
    return None


def get_template_badge_style(source: str) -> str:
    """Return a QSS-compatible style string for the template badge.

    Args:
        source: The template source field ('marketplace', 'builtin', or 'user').

    Returns:
        A QSS inline style snippet suitable for setStyleSheet() on a QLabel badge.
        Returns empty string for user templates (no badge).
    """
    normalized = source.strip().lower()
    if normalized == "marketplace":
        return (
            "background-color: #7c3aed;"
            " color: #ffffff;"
            " border-radius: 4px;"
            " padding: 2px 8px;"
            " font-size: 11px;"
            " font-weight: bold;"
        )
    if normalized == "builtin":
        return (
            "background-color: #6b7280;"
            " color: #ffffff;"
            " border-radius: 4px;"
            " padding: 2px 8px;"
            " font-size: 11px;"
            " font-weight: bold;"
        )
    return ""


def should_confirm_delete(source: str) -> bool:
    """Determine whether deleting a template requires a confirmation dialog.

    Marketplace templates require confirmation because they would need to be
    reinstalled from the marketplace catalog after deletion.

    Args:
        source: The template source field ('marketplace', 'builtin', or 'user').

    Returns:
        True for marketplace templates, False otherwise.
    """
    return source.strip().lower() == "marketplace"
