"""Logo ↔ spectrum binding helpers — port of logoSpectrumBindings.ts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from features.video.lib.video_template_draft import get_recommended_spectrum_logo_gap

AnchorFn = Callable[[str, float, float, int, int], tuple[float, float]]
LogoShape = Literal["circle", "square"]


@dataclass(frozen=True)
class LogoBounds:
    """Minimal Logo → Spectrum coupling DTO (Phase 3 shape follow)."""

    cx: float
    cy: float
    half_w: float
    half_h: float
    shape: LogoShape
    visible_radius_ratio: float = 1.0
    gap_px: float = 0.0
    attached: bool = False

    def outer_half_extents(self) -> tuple[float, float]:
        """Path half-size after visible-content ratio + outer gap (pre layer offset)."""
        ratio = float(max(0.05, min(1.0, self.visible_radius_ratio)))
        gap = float(max(0.0, self.gap_px))
        return (
            float(max(0.0, self.half_w * ratio + gap)),
            float(max(0.0, self.half_h * ratio + gap)),
        )


def normalize_logo_shape(shape: str | None = None, *, circle_mask: bool | None = None) -> LogoShape:
    if circle_mask is not None:
        return "circle" if bool(circle_mask) else "square"
    s = str(shape or "circle").lower().strip()
    if s in ("square", "rect", "rectangle"):
        return "square"
    return "circle"


def build_logo_bounds(
    *,
    cx: float,
    cy: float,
    logo_half_size: float,
    shape: str | None = None,
    circle_mask: bool | None = None,
    visible_radius_ratio: float = 1.0,
    gap_px: float = 0.0,
    attached: bool = False,
) -> LogoBounds:
    half = float(max(0.0, logo_half_size))
    return LogoBounds(
        cx=float(cx),
        cy=float(cy),
        half_w=half,
        half_h=half,
        shape=normalize_logo_shape(shape, circle_mask=circle_mask),
        visible_radius_ratio=float(max(0.05, min(1.0, visible_radius_ratio))),
        gap_px=float(max(0.0, gap_px)),
        attached=bool(attached),
    )


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
