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

# Studio / document ids for composition.logo.maskShape
MASK_SHAPE_AUTO = "auto"
MASK_SHAPE_SQUARE = "square"
MASK_SHAPE_CIRCLE = "circle"
MASK_SHAPE_TRIANGLE = "triangle"
MASK_SHAPE_HEXAGON = "hexagon"
MASK_SHAPE_DIAMOND = "diamond"
MASK_SHAPE_HEART = "heart"

CENTER_IMAGE_MASK_OPTIONS: tuple[tuple[str, str], ...] = (
    (MASK_SHAPE_AUTO, "Match spectrum"),
    (MASK_SHAPE_SQUARE, "Square"),
    (MASK_SHAPE_CIRCLE, "Circle"),
    (MASK_SHAPE_TRIANGLE, "Triangle"),
    (MASK_SHAPE_HEXAGON, "Hexagon"),
    (MASK_SHAPE_DIAMOND, "Diamond"),
    (MASK_SHAPE_HEART, "Heart"),
)

_EXPLICIT_MASK: dict[str, int] = {
    MASK_SHAPE_SQUARE: LOGO_MASK_NONE,
    "none": LOGO_MASK_NONE,
    MASK_SHAPE_CIRCLE: LOGO_MASK_CIRCLE,
    MASK_SHAPE_TRIANGLE: LOGO_MASK_TRIANGLE,
    MASK_SHAPE_DIAMOND: LOGO_MASK_DIAMOND,
    MASK_SHAPE_HEXAGON: LOGO_MASK_HEXAGON,
    MASK_SHAPE_HEART: LOGO_MASK_HEART,
}

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
    "rect": LOGO_MASK_NONE,
}


def normalize_logo_mask_shape_id(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in ("", "none", "null"):
        return MASK_SHAPE_AUTO
    if raw in _EXPLICIT_MASK or raw == MASK_SHAPE_AUTO:
        return raw
    if raw in ("sq", "box", "rect", "rectangle"):
        return MASK_SHAPE_SQUARE
    return MASK_SHAPE_AUTO


def resolve_logo_mask_mode(
    spectrum_shape: str | None,
    *,
    mask_shape: str | None = None,
    fit_to_shape: bool = True,
    circle_mask: bool = False,
) -> int:
    """Pick GPU logo mask.

    ``mask_shape`` (Studio): ``auto`` follows spectrum when ``fit_to_shape``;
    explicit square/circle/triangle/hex/diamond/heart always wins.
    """
    explicit = normalize_logo_mask_shape_id(mask_shape)
    if explicit != MASK_SHAPE_AUTO:
        return int(_EXPLICIT_MASK.get(explicit, LOGO_MASK_NONE))

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
    # Prefer geometry ids on layers — never stylePreset (render style ≠ path).
    layers = tpl.get("spectrumLayers") if isinstance(tpl.get("spectrumLayers"), list) else []
    for layer in layers:
        if not isinstance(layer, dict) or not bool(layer.get("enabled", True)):
            continue
        for key in ("shapeId", "pathMode", "shape"):
            raw = layer.get(key)
            if raw not in (None, "", "none", "auto"):
                return str(raw)
        break
    for key in ("spectrumShape", "style"):
        raw = tpl.get(key)
        if raw not in (None, "", "none"):
            return str(raw)
    return None


def apply_logo_mask_uniform(prog_logo: Any, mode: int) -> None:
    """Set logo mask on a compiled program (new ``logo_mask_mode`` or legacy circle)."""
    try:
        mode_i = int(mode)
    except (TypeError, ValueError):
        mode_i = LOGO_MASK_NONE
    if prog_logo is None:
        return
    # Prefer direct assignment — ``in prog`` can miss uniforms on some ModernGL builds.
    try:
        prog_logo["logo_mask_mode"].value = mode_i
        return
    except Exception:
        pass
    try:
        prog_logo["logo_circle_mask"].value = 1 if mode_i == LOGO_MASK_CIRCLE else 0
    except Exception:
        pass


def apply_logo_frame_size_uniform(prog_logo: Any, frame_size_px: float) -> None:
    """Crop aperture in px (spectrum shape frame). ``0`` = follow Image size (legacy)."""
    if prog_logo is None:
        return
    try:
        size = float(frame_size_px)
    except (TypeError, ValueError):
        size = 0.0
    size = float(max(0.0, size))
    try:
        prog_logo["logo_frame_size_px"].value = (size, size)
    except Exception:
        pass


def apply_logo_rotation_uniforms(
    prog_logo: Any,
    *,
    content_deg: float = 0.0,
    mask_deg: float = 0.0,
    spin_rad: float = 0.0,
) -> None:
    """Set image content rotation vs shape/mask rotation (degrees + optional spin rad).

    Angles use the same convention as spectrum ``rotate_spectrum_bases`` (shared
    GL/py space: negative Y is the triangle tip / path ``rotation=-PI/2``).
    """
    if prog_logo is None:
        return
    try:
        content = float(content_deg) % 360.0
        if content < 0.0:
            content += 360.0
    except (TypeError, ValueError):
        content = 0.0
    try:
        mask = float(mask_deg) % 360.0
        if mask < 0.0:
            mask += 360.0
    except (TypeError, ValueError):
        mask = 0.0
    try:
        spin = float(spin_rad)
    except (TypeError, ValueError):
        spin = 0.0
    content_rad = content * 0.017453292519943295 + spin
    mask_rad = mask * 0.017453292519943295
    try:
        prog_logo["logo_rot_rad"].value = float(content_rad)
    except Exception:
        pass
    try:
        prog_logo["logo_mask_rot_rad"].value = float(mask_rad)
    except Exception:
        pass


def logo_frame_size_for_mask(*, mask_mode: int, shape_radius_px: float) -> float:
    """Screen-space crop diameter for a masked center image."""
    try:
        mode = int(mask_mode)
    except (TypeError, ValueError):
        mode = LOGO_MASK_NONE
    if mode <= LOGO_MASK_NONE:
        return 0.0
    try:
        radius = float(shape_radius_px)
    except (TypeError, ValueError):
        return 0.0
    if radius <= 1.0:
        return 0.0
    return float(radius * 2.0)
