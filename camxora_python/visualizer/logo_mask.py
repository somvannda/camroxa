"""Center-image / logo mask modes — clip texture to spectrum geometry."""

from __future__ import annotations

from typing import Any

# GLSL ``logo_mask_mode`` values (must stay in sync with fs_logo).
LOGO_MASK_NONE = 0
LOGO_MASK_CIRCLE = 1
LOGO_MASK_TRIANGLE = 2
LOGO_MASK_DIAMOND = 3
LOGO_MASK_HEXAGON = 4
LOGO_MASK_HEART = 5

_SHAPE_TO_MASK: dict[str, int] = {
    "circle": LOGO_MASK_CIRCLE,
    "double_circle": LOGO_MASK_CIRCLE,
    "ring": LOGO_MASK_CIRCLE,
    "starburst": LOGO_MASK_CIRCLE,
    "wave": LOGO_MASK_CIRCLE,
    "audio_ribbon": LOGO_MASK_CIRCLE,
    "spiral": LOGO_MASK_CIRCLE,
    "tunnel": LOGO_MASK_CIRCLE,
    "infinity": LOGO_MASK_CIRCLE,
    "triangle": LOGO_MASK_TRIANGLE,
    "diamond": LOGO_MASK_DIAMOND,
    "hexagon": LOGO_MASK_HEXAGON,
    "heart": LOGO_MASK_HEART,
    "bars": LOGO_MASK_NONE,
    "soft_eq": LOGO_MASK_NONE,
}


def resolve_logo_mask_mode(
    spectrum_shape: str | None,
    *,
    fit_to_shape: bool = True,
    circle_mask: bool = False,
) -> int:
    """Pick GPU logo mask from spectrum shape (Vizzy-style fit).

    When ``fit_to_shape`` is True, clip the square image to the active spectrum
    geometry (triangle/hex/heart/…). Otherwise fall back to legacy circleMask.
    """
    if not fit_to_shape:
        return LOGO_MASK_CIRCLE if bool(circle_mask) else LOGO_MASK_NONE
    try:
        from visualizer.presets.shapes import normalize_spectrum_shape_id

        key = normalize_spectrum_shape_id(spectrum_shape)
    except Exception:
        key = None
    if key is None:
        raw = str(spectrum_shape or "").strip().lower().replace("-", "_").replace(" ", "_")
        key = raw if raw in _SHAPE_TO_MASK else None
    if key is None:
        return LOGO_MASK_CIRCLE if bool(circle_mask) else LOGO_MASK_NONE
    return int(_SHAPE_TO_MASK.get(key, LOGO_MASK_CIRCLE))


def spectrum_shape_from_template(template: dict[str, Any] | None) -> str | None:
    """Best-effort spectrum shape id from a renderer / composition template."""
    tpl = template if isinstance(template, dict) else {}
    engine = tpl.get("engine") if isinstance(tpl.get("engine"), dict) else {}
    spec_eng = engine.get("spectrum") if isinstance(engine.get("spectrum"), dict) else {}
    shape = spec_eng.get("shape")
    if shape not in (None, "", "none"):
        return str(shape)
    comp = tpl.get("composition") if isinstance(tpl.get("composition"), dict) else {}
    spec = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
    shape = spec.get("shape")
    if shape not in (None, "", "none"):
        return str(shape)
    return None


def apply_logo_mask_uniform(prog_logo: Any, mode: int) -> None:
    """Set logo mask on a compiled program (new ``logo_mask_mode`` or legacy circle)."""
    try:
        mode_i = int(mode)
    except (TypeError, ValueError):
        mode_i = LOGO_MASK_NONE
    if prog_logo is None:
        return
    try:
        if "logo_mask_mode" in prog_logo:
            prog_logo["logo_mask_mode"].value = mode_i
            return
    except Exception:
        pass
    try:
        if "logo_circle_mask" in prog_logo:
            prog_logo["logo_circle_mask"].value = 1 if mode_i == LOGO_MASK_CIRCLE else 0
    except Exception:
        pass
