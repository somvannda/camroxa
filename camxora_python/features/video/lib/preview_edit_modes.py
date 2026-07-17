"""Preview canvas edit-mode resolution for domain and side tabs."""

from __future__ import annotations


def resolve_preview_edit_modes(
    active_domain_tab: str,
    active_side_tab: str = "",
    *,
    edit_focus: str = "domain",
) -> tuple[bool, bool, str]:
    """Return `(background_edit, spectrum_position_edit, text_domain_edit)`.

    ``text_domain_edit`` is ``\"album\"``, ``\"title\"``, or ``\"\"``.
    ``edit_focus`` is ``\"domain\"`` (left rail) or ``\"side\"`` (right rail).
    The last-focused rail wins so Album/Title drag does not permanently
    block Spectrum/Background drag.
    """
    focus = str(edit_focus or "domain").strip().lower()
    side = str(active_side_tab or "").strip().lower()
    if focus == "side" and side in {"album", "title"}:
        return False, False, side

    tab = str(active_domain_tab or "").strip().lower()
    if tab == "background":
        return True, False, ""
    if tab == "spectrum":
        return False, True, ""
    return False, False, ""
