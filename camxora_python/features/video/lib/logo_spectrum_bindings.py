"""Logo ↔ spectrum binding helpers — port of logoSpectrumBindings.ts."""

from __future__ import annotations

from typing import Any

from features.video.lib.video_template_draft import get_recommended_spectrum_logo_gap


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
