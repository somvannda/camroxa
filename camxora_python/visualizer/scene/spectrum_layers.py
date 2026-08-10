"""Studio spectrum ring-layer helpers — each layer owns its own controls."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.presets.audio_buses import normalize_audio_bus_id

# Keys stamped from authored rings onto render layers.
_LAYER_CONTROL_KEYS: tuple[str, ...] = (
    "barHeight",
    "barWidthScale",
    "thicknessScale",
    "barCount",
    "tipTaper",
    "mirrored",
    "gravity",
    "peakCapsEnabled",
    "solidBand",
    "glow",
    "blur",
)


def default_spectrum_layer(index: int = 0, *, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "name": f"Ring {int(index) + 1}",
        "radiusOffset": float(index) * 18.0,
        "opacity": 1.0,
        "enabled": True,
        "audioBus": None,  # None = overall / shared spectrum audio
        "audioGain": 1.0,
        "barHeight": 1.0,
        "barWidthScale": 1.0,
        "thicknessScale": 1.0,
        "barCount": 64,
        "tipTaper": 0.0,
        "mirrored": None,  # None = shape default
        "gravity": None,  # None = shape default
        "peakCapsEnabled": False,
        "solidBand": False,
        "glow": None,  # None = inherit spectrum/material glow
        "blur": None,
    }
    if isinstance(defaults, dict):
        for key, value in defaults.items():
            if key in base or key in _LAYER_CONTROL_KEYS:
                base[key] = value
    return base


def spectrum_layer_defaults_from_comp(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Seed new layers from (legacy) spectrum-level knobs when present."""
    spec = spec if isinstance(spec, dict) else {}
    try:
        bar_count = int(round(max(24, min(160, float(spec.get("barCount") or 64)))))
    except (TypeError, ValueError):
        bar_count = 64
    out: dict[str, Any] = {
        "barHeight": _clamp_float(spec.get("barHeight"), 0.25, 4.0, 1.0),
        "barWidthScale": _clamp_float(spec.get("barWidthScale"), 0.08, 3.0, 1.0),
        "thicknessScale": _clamp_float(spec.get("thicknessScale"), 0.25, 3.0, 1.0),
        "barCount": bar_count,
        "tipTaper": _clamp_float(spec.get("tipTaper"), 0.0, 1.0, 0.0),
        "peakCapsEnabled": bool(spec.get("peakCapsEnabled", False)),
        "solidBand": bool(spec.get("solidBand", False)),
    }
    if spec.get("mirrored") is None:
        out["mirrored"] = None
    else:
        out["mirrored"] = bool(spec.get("mirrored"))
    grav = spec.get("gravity")
    if grav in (None, "", "none", "auto"):
        out["gravity"] = None
    else:
        try:
            from visualizer._spectrum_fast import normalize_spectrum_gravity

            out["gravity"] = normalize_spectrum_gravity(grav)
        except Exception:
            out["gravity"] = None
    return out


def normalize_spectrum_layers(
    raw: Any,
    *,
    defaults: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    seed = spectrum_layer_defaults_from_comp(defaults) if defaults else {}
    if not isinstance(raw, list) or not raw:
        return [default_spectrum_layer(0, defaults=seed)]
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        merged = default_spectrum_layer(len(out), defaults=seed)
        merged.update({k: v for k, v in item.items() if v is not None or k in ("audioBus", "mirrored", "gravity", "glow", "blur")})
        try:
            gap = float(merged.get("radiusOffset") or 0.0)
        except (TypeError, ValueError):
            gap = 0.0
        gap = max(-200.0, min(400.0, gap))
        try:
            opacity = float(merged.get("opacity") if merged.get("opacity") is not None else 1.0)
        except (TypeError, ValueError):
            opacity = 1.0
        opacity = max(0.05, min(1.0, opacity))
        try:
            audio_gain = float(merged.get("audioGain") if merged.get("audioGain") is not None else 1.0)
        except (TypeError, ValueError):
            audio_gain = 1.0
        audio_gain = max(0.0, min(3.0, audio_gain))
        name = str(merged.get("name") or "").strip() or f"Ring {len(out) + 1}"
        name = name[:48]
        try:
            bar_count = int(round(max(24, min(160, float(merged.get("barCount") or 64)))))
        except (TypeError, ValueError):
            bar_count = 64
        mirrored = merged.get("mirrored")
        if mirrored in (None, "", "auto", "none"):
            mirrored = None
        else:
            mirrored = bool(mirrored)
        gravity = merged.get("gravity")
        if gravity in (None, "", "auto", "none"):
            gravity = None
        else:
            try:
                from visualizer._spectrum_fast import normalize_spectrum_gravity

                gravity = normalize_spectrum_gravity(gravity)
            except Exception:
                gravity = None
        glow = merged.get("glow")
        if glow is not None:
            glow = _clamp_float(glow, 0.0, 1.0, 0.45)
        blur = merged.get("blur")
        if blur is not None:
            blur = _clamp_float(blur, 0.0, 8.0, 0.0)
        out.append(
            {
                "name": name,
                "radiusOffset": gap,
                "opacity": opacity,
                "enabled": bool(merged.get("enabled", True)),
                "audioBus": normalize_audio_bus_id(merged.get("audioBus")),
                "audioGain": audio_gain,
                "barHeight": _clamp_float(merged.get("barHeight"), 0.25, 4.0, 1.0),
                "barWidthScale": _clamp_float(merged.get("barWidthScale"), 0.08, 3.0, 1.0),
                "thicknessScale": _clamp_float(merged.get("thicknessScale"), 0.25, 3.0, 1.0),
                "barCount": bar_count,
                "tipTaper": _clamp_float(merged.get("tipTaper"), 0.0, 1.0, 0.0),
                "mirrored": mirrored,
                "gravity": gravity,
                "peakCapsEnabled": bool(merged.get("peakCapsEnabled", False)),
                "solidBand": bool(merged.get("solidBand", False)),
                "glow": glow,
                "blur": blur,
            }
        )
        if len(out) >= 12:
            break
    return out or [default_spectrum_layer(0, defaults=seed)]


def expand_spectrum_layers(
    template_layers: list[dict[str, Any]],
    authored_rings: list[dict[str, Any]],
    *,
    size_scale: float = 1.0,
    defaults: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Merge shape templates with authored rings — each ring keeps its own controls."""
    try:
        scale = max(0.35, min(2.5, float(size_scale)))
    except (TypeError, ValueError):
        scale = 1.0
    templates = [dict(x) for x in template_layers if isinstance(x, dict)]
    rings = normalize_spectrum_layers(authored_rings, defaults=defaults)
    enabled = [r for r in rings if bool(r.get("enabled", True))]
    if not enabled:
        enabled = [default_spectrum_layer(0, defaults=defaults)]

    def _stamp_controls(layer: dict[str, Any], ring: dict[str, Any]) -> None:
        layer["audioBus"] = ring.get("audioBus")
        layer["audioGain"] = float(ring.get("audioGain") if ring.get("audioGain") is not None else 1.0)
        layer["barHeight"] = float(ring.get("barHeight") or 1.0)
        layer["barWidthScale"] = float(ring.get("barWidthScale") or 1.0)
        layer["thicknessScale"] = float(ring.get("thicknessScale") or 1.0)
        layer["barCount"] = int(ring.get("barCount") or 64)
        layer["tipTaper"] = float(ring.get("tipTaper") or 0.0)
        layer["peakCapsEnabled"] = bool(ring.get("peakCapsEnabled", False))
        layer["solidBand"] = bool(ring.get("solidBand", False))
        if ring.get("mirrored") is not None:
            layer["mirrored"] = bool(ring.get("mirrored"))
        if ring.get("gravity") is not None:
            layer["gravity"] = ring.get("gravity")
        if ring.get("glow") is not None:
            lg = float(ring.get("glow"))
            layer["layerGlow"] = lg
            # Preview treats glow as 0–100.
            layer["glow"] = lg * 100.0
        if ring.get("blur") is not None:
            layer["layerBlur"] = float(ring.get("blur"))
            layer["blur"] = float(ring.get("blur"))
        # Apply width/thickness scales onto geometry bases from the shape template.
        try:
            base_bw = float(layer.get("barWidth") or 4.0)
        except (TypeError, ValueError):
            base_bw = 4.0
        try:
            base_th = float(layer.get("thickness") or 36.0)
        except (TypeError, ValueError):
            base_th = 36.0
        bh = float(ring.get("barHeight") or 1.0)
        layer["barWidth"] = max(0.15, base_bw * float(ring.get("barWidthScale") or 1.0))
        layer["thickness"] = max(4.0, base_th * float(ring.get("thicknessScale") or 1.0) * bh)

    if len(enabled) <= 1 and templates:
        ring = enabled[0]
        extra = float(ring.get("radiusOffset") or 0.0)
        ring_op = float(ring.get("opacity") or 1.0)
        out: list[dict[str, Any]] = []
        for tl in templates:
            layer = deepcopy(tl)
            base = float(layer.get("radiusOffset") or 0.0)
            layer["radiusOffset"] = (base + extra) * scale
            layer["opacity"] = float(layer.get("opacity") or 1.0) * ring_op
            layer["name"] = str(ring.get("name") or layer.get("name") or "Ring 1")
            layer["sizeScale"] = scale
            _stamp_controls(layer, ring)
            out.append(layer)
        return out

    proto = deepcopy(templates[0]) if templates else {
        "curved": True,
        "mirrored": False,
        "barWidth": 4.0,
        "thickness": 36.0,
        "gravity": "outward",
        "glow": 0.0,
        "blur": 0.0,
        "opacity": 1.0,
        "radiusOffset": 0.0,
        "shapeId": "none",
    }
    out = []
    for ring in enabled:
        layer = deepcopy(proto)
        layer["name"] = str(ring.get("name") or "Ring")
        layer["radiusOffset"] = float(ring.get("radiusOffset") or 0.0) * scale
        layer["opacity"] = float(ring.get("opacity") or 1.0)
        layer["sizeScale"] = scale
        _stamp_controls(layer, ring)
        out.append(layer)
    return out


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return float(default)
