"""Logo ↔ spectrum binding helpers — port of logoSpectrumBindings.ts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from features.video.lib.video_template_draft import get_recommended_spectrum_logo_gap

AnchorFn = Callable[[str, float, float, int, int], tuple[float, float]]


def apply_logo_shape_draft_change(draft: dict[str, Any], logo_shape: str) -> dict[str, Any]:
    attach = bool(draft.get("spectrumAttachToLogo"))
    size_step = float(draft.get("logoSizeStep") or 1)
    return {
        **draft,
        "logoShape": logo_shape,
        "spectrumLogoGap": get_recommended_spectrum_logo_gap(logo_shape, size_step)
        if attach
        else draft.get("spectrumLogoGap"),
    }


def apply_logo_size_draft_change(draft: dict[str, Any], logo_size_step: float) -> dict[str, Any]:
    return {**draft, "logoSizeStep": logo_size_step}


def apply_spectrum_attach_to_logo_draft_change(draft: dict[str, Any], attach: bool) -> dict[str, Any]:
    logo_shape = str(draft.get("logoShape") or "circle")
    size_step = float(draft.get("logoSizeStep") or 1)
    return {
        **draft,
        "spectrumAttachToLogo": attach,
        "spectrumLogoGap": get_recommended_spectrum_logo_gap(logo_shape, size_step)
        if attach
        else draft.get("spectrumLogoGap"),
    }


def resolve_spectrum_logo_centers(
    get_anchor_coords: AnchorFn,
    *,
    w: int,
    h: int,
    sf: float,
    position: dict[str, Any] | None,
    spectrum_attach_to_logo: bool,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return ``(spectrum_center, logo_center)`` in pixel space.

    When attached, both share the spectrum position so the ring follows the logo.
    When detached, spectrum uses ``position`` and the logo stays frame-centered.
    """
    pos = position if isinstance(position, dict) else {}
    anchor = str(pos.get("anchor") or "center")
    try:
        ox = float(pos.get("x", 0.0) or 0.0) * float(sf)
    except (TypeError, ValueError):
        ox = 0.0
    try:
        oy = float(pos.get("y", 0.0) or 0.0) * float(sf)
    except (TypeError, ValueError):
        oy = 0.0
    spectrum = get_anchor_coords(anchor, ox, oy, int(w), int(h))
    if spectrum_attach_to_logo:
        return spectrum, spectrum
    logo = get_anchor_coords("center", 0.0, 0.0, int(w), int(h))
    return spectrum, logo
