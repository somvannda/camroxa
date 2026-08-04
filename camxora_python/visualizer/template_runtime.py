"""Renderer template defaults and normalization for GPU preview."""

from __future__ import annotations

import copy
import json
from typing import Any


def _normalize_layer_path_mode(value: Any) -> str:
    v = str(value or "auto").lower().strip()
    if v in ("rectangle", "square"):
        return "rect"
    if v in ("auto", "circle", "rect"):
        return v
    return "auto"


def default_renderer_template() -> dict:
    return {
        "templateName": "New Template",
        "style": "orbit-spikes",
        "logoPath": "",
        "spectrumEnabled": True,
        "layers": [
            {
                "id": "base-layer",
                "name": "Base Ring",
                "curved": False,
                "mirrored": False,
                "fillCircle": False,
                "solidBand": False,
                "thickness": 36,
                "barWidth": 5,
                "barCount": 64,
                "radiusOffset": 0,
                "gravity": "top",
                "color": {
                    "mode": "gradient",
                    "solidColor": "#ff4fd8",
                    "gradientColors": ["#ffffff", "#ff4fd8", "#22d3ee"],
                    "gradientDirection": "left-to-right",
                },
                "glow": 0,
                "blur": 0,
                "rotation": 0,
                "blend_mode": "normal",
                "opacity": 1,
                "peakCapsEnabled": False,
                "peakCapColor": "#ffffff",
                "peakCapGap": 4.0,
                "peakCapThickness": 3.0,
                "peakCapDecay": 0.92,
                "pathMode": "auto",
            }
        ],
        "globalColor": {
            "mode": "solid",
            "solidColor": "#ffffff",
            "gradientColors": ["#ff00ff", "#00ffff"],
            "gradientDirection": "left-to-right",
        },
        "position": {"anchor": "center", "x": 0, "y": 0},
        "previewBindings": {
            "spectrumAttachToLogo": True,
            "spectrumLogoGap": 0.0,
        },
        "renderBaseHeight": 450,
        "audioSettings": {"sensitivity": 1.0, "smoothing": 0.8, "bounce": 0, "minHeight": 0.1, "peakHold": 0},
        "backgroundSettings": {
            "brightness": 1.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "hue": 0.0,
            "reactivity": 0.0,
            "smoothing": 0.8,
            "motionMode": "none",
            "motionZoomStrength": 1.0,
            "motionVibrateStrength": 1.0,
            "fitMode": "cover",
            "userScale": 1.0,
            "userOffsetX": 0.0,
            "userOffsetY": 0.0,
        },
        "logoSettings": {
            "enabled": True,
            "size": 200,
            "scale": 1.0,
            "opacity": 1.0,
            "circleMask": True,
            "reactivity": 0.5,
            "smoothing": 0.75,
            "spinEnabled": False,
            "spinDirection": "cw",
            "spinSpeed": 0.0,
            "position": {"anchor": "center", "x": 0, "y": 0},
        },
        "particlesSettings": {
            "enabled": True,
            "maxCount": 3000,
            "spawnRate": 40,
            "lifetimeSec": 1.6,
            "speed": 15,
            "reactivity": 0.5,
            "smoothing": 0.65,
            "size": 2,
            "sizeJitter": 0.0,
            "drift": 0.0,
            "swirl": 0.0,
            "spawnArea": "centerRing",
            "variant": "classic",
            "opacity": 0.35,
            "color": "#ffffff",
            "spawnMode": "always",
            "spawnTrigger": "both",
            "spawnThreshold": 0.15,
            "reactColor": "#ffffff",
            "reactStrength": 0.65,
            "style": "dot",
            "glow": 0.0,
            "trailEnabled": False,
            "trailLength": 8,
            "trailFade": 0.65,
            "trailWidth": 0.45,
        },
        "effects": {
            "vignette": {"enabled": False, "strength": 0.35, "feather": 0.65, "color": "#000000", "opacity": 0.65, "reactivity": 0.0},
            "smoke": {"enabled": False, "strength": 0.35, "blur": 0.55, "noise": 0.55, "speed": 0.35, "color": "#000000", "opacity": 0.55},
        },
        "lightningEnabled": False,
        "lightningLayers": [
            {
                "id": "lightning-1",
                "name": "Bolt 1",
                "enabled": True,
                "style": "fork",
                "x": 0.0,
                "y": 0.0,
                "direction": "down",
                "rotation": 0.0,
                "color": {
                    "mode": "gradient",
                    "solidColor": "#e0f2fe",
                    "gradientColors": ["#ffffff", "#7dd3fc", "#38bdf8"],
                },
                "opacity": 0.85,
                "intensity": 0.72,
                "reactivity": 0.55,
                "speed": 1.0,
                "flashRate": 0.85,
                "thickness": 2.8,
                "glow": 0.5,
                "branchiness": 0.55,
                "blend": "add",
                "length": 200.0,
            }
        ],
        "textOverlays": [],
    }


def _is_obj(x: Any) -> bool:
    return isinstance(x, dict)


def normalize_renderer_template(input_template: Any) -> dict:
    base = default_renderer_template()
    if not _is_obj(input_template):
        return copy.deepcopy(base)

    out = copy.deepcopy(base)
    out.update({k: v for k, v in input_template.items() if k in out or k in ("previewBackground", "previewLogo")})

    pos_in = input_template.get("position") if _is_obj(input_template.get("position")) else {}
    out["position"] = {**base["position"], **pos_in}

    preview_bindings_in = input_template.get("previewBindings") if _is_obj(input_template.get("previewBindings")) else {}
    out["previewBindings"] = {**base["previewBindings"], **preview_bindings_in}

    audio_in = input_template.get("audioSettings") if _is_obj(input_template.get("audioSettings")) else {}
    out["audioSettings"] = {**base["audioSettings"], **audio_in}

    bg_in = input_template.get("backgroundSettings") if _is_obj(input_template.get("backgroundSettings")) else {}
    out["backgroundSettings"] = {**base["backgroundSettings"], **bg_in}

    logo_in = input_template.get("logoSettings") if _is_obj(input_template.get("logoSettings")) else {}
    logo_pos_in = logo_in.get("position") if _is_obj(logo_in.get("position")) else {}
    out["logoSettings"] = {**base["logoSettings"], **logo_in, "position": {**base["logoSettings"]["position"], **logo_pos_in}}

    ps_in = input_template.get("particlesSettings") if _is_obj(input_template.get("particlesSettings")) else {}
    if not ps_in and _is_obj(input_template.get("particles")):
        ps_in = input_template.get("particles") or {}
    out["particlesSettings"] = {**base["particlesSettings"], **ps_in}

    gc_in = input_template.get("globalColor") if _is_obj(input_template.get("globalColor")) else {}
    out["globalColor"] = {**base["globalColor"], **gc_in}

    rbh = out.get("renderBaseHeight")
    if not isinstance(rbh, (int, float)):
        out["renderBaseHeight"] = 450

    ps = out["particlesSettings"]
    ps["enabled"] = bool(ps.get("enabled", True))
    if not isinstance(ps.get("maxCount"), (int, float)) and isinstance(ps.get("count"), (int, float)):
        ps["maxCount"] = ps.get("count")
    if not isinstance(ps.get("spawnRate"), (int, float)) and isinstance(ps.get("spawn_rate"), (int, float)):
        ps["spawnRate"] = ps.get("spawn_rate")
    if not isinstance(ps.get("lifetimeSec"), (int, float)) and isinstance(ps.get("lifetime_sec"), (int, float)):
        ps["lifetimeSec"] = ps.get("lifetime_sec")
    if not isinstance(ps.get("opacity"), (int, float)) and isinstance(ps.get("alpha"), (int, float)):
        ps["opacity"] = ps.get("alpha")

    ps["speed"] = float(max(0.2, min(25, float(ps.get("speed", 1)))))
    ps["reactivity"] = float(max(0.0, min(1.0, float(ps.get("reactivity", 0.1)))))
    ps["smoothing"] = float(max(0.0, min(0.99, float(ps.get("smoothing", 0.65)))))
    ps["opacity"] = float(max(0.0, min(1.0, float(ps.get("opacity", 0.35)))))
    ps["maxCount"] = int(max(200, min(2000, int(ps.get("maxCount", 200)))))
    ps["spawnRate"] = float(max(50, min(1500, float(ps.get("spawnRate", 100)))))
    ps["spawnMode"] = "reactiveOnly" if str(ps.get("spawnMode", "always")) == "reactiveOnly" else "always"
    ps["spawnTrigger"] = str(ps.get("spawnTrigger", "both"))
    if ps["spawnTrigger"] not in ("kick", "bass", "both"):
        ps["spawnTrigger"] = "both"
    ps["spawnThreshold"] = float(max(0.0, min(1.0, float(ps.get("spawnThreshold", 0.15) or 0.15))))
    ps["reactColor"] = str(ps.get("reactColor", "#ffffff") or "#ffffff")
    ps["colorMode"] = "palette" if str(ps.get("colorMode", "solid") or "solid") == "palette" else "solid"
    palette_raw = ps.get("paletteColors")
    if isinstance(palette_raw, list):
        from features.video.lib.particle_color_engine import normalize_particle_palette_colors

        ps["paletteColors"] = normalize_particle_palette_colors(
            palette_raw,
            str(ps.get("color", "#ffffff") or "#ffffff"),
            require_stops=(ps["colorMode"] == "palette"),
        )
    else:
        ps["paletteColors"] = []
    ps["reactStrength"] = float(max(0.0, min(1.0, float(ps.get("reactStrength", 0.65) or 0.65))))
    ps["sizeJitter"] = float(max(0.0, min(1.0, float(ps.get("sizeJitter", 0.0) or 0.0))))
    ps["drift"] = float(max(0.0, min(1.0, float(ps.get("drift", 0.0) or 0.0))))
    ps["swirl"] = float(max(0.0, min(1.0, float(ps.get("swirl", 0.0) or 0.0))))
    ps["spawnArea"] = str(ps.get("spawnArea", "centerRing") or "centerRing")
    if ps["spawnArea"] not in ("centerRing", "bottom", "edges", "full", "screenCenter", "screenRandom"):
        ps["spawnArea"] = "centerRing"
    ps["travelMode"] = str(ps.get("travelMode", "spawnFlow") or "spawnFlow")
    if ps["travelMode"] not in ("spawnFlow", "rise", "fall", "burst", "random"):
        ps["travelMode"] = "spawnFlow"
    ps["variant"] = str(ps.get("variant", "classic") or "classic")
    if ps["variant"] not in ("classic", "bokeh", "soap", "dust"):
        ps["variant"] = "classic"
    ps["style"] = str(ps.get("style", "dot"))
    if ps["style"] not in ("dot", "glow", "ring", "spark", "bokeh", "music"):
        ps["style"] = "dot"
    try:
        ps["glow"] = float(max(0.0, min(1.0, float(ps.get("glow", 0.0) or 0.0))))
    except (TypeError, ValueError):
        ps["glow"] = 0.0
    ps["trailEnabled"] = bool(ps.get("trailEnabled", False))
    try:
        trail_len = int(round(float(ps.get("trailLength", 8) or 8)))
    except (TypeError, ValueError):
        trail_len = 8
    ps["trailLength"] = int(max(2, min(24, trail_len)))
    ps["trailFade"] = float(max(0.05, min(0.98, float(ps.get("trailFade", 0.65) or 0.65))))
    ps["trailWidth"] = float(max(0.1, min(1.0, float(ps.get("trailWidth", 0.45) or 0.45))))

    bg = out["backgroundSettings"]
    bg["brightness"] = float(max(0.0, min(3.0, float(bg.get("brightness", 1.0)))))
    bg["contrast"] = float(max(0.0, min(2.0, float(bg.get("contrast", 1.0) or 1.0))))
    bg["saturation"] = float(max(0.0, min(2.0, float(bg.get("saturation", 1.0) or 1.0))))
    bg["hue"] = float(max(-180.0, min(180.0, float(bg.get("hue", 0.0) or 0.0))))
    # Match Background inspector ranges (0–20) so Zoom Strength / Reactivity
    # are not silently crushed before preview/export.
    bg["reactivity"] = float(max(0.0, min(20.0, float(bg.get("reactivity", 0.0)))))
    bg["smoothing"] = float(max(0.0, min(0.99, float(bg.get("smoothing", 0.8)))))
    bg["motionMode"] = str(bg.get("motionMode", "none") or "none")
    if bg["motionMode"] not in ("none", "zoom", "vibrate", "both"):
        bg["motionMode"] = "none"
    bg["motionZoomStrength"] = float(max(0.0, min(20.0, float(bg.get("motionZoomStrength", 1.0) or 1.0))))
    bg["motionVibrateStrength"] = float(max(0.0, min(20.0, float(bg.get("motionVibrateStrength", 1.0) or 1.0))))
    bg["fitMode"] = str(bg.get("fitMode", "cover") or "cover")
    if bg["fitMode"] not in ("cover", "contain", "original"):
        bg["fitMode"] = "cover"
    try:
        bg["userScale"] = float(bg.get("userScale", 1.0) or 1.0)
    except Exception:
        bg["userScale"] = 1.0
    bg["userScale"] = float(max(0.05, min(20.0, float(bg.get("userScale", 1.0) or 1.0))))
    try:
        bg["userOffsetX"] = float(bg.get("userOffsetX", 0.0) or 0.0)
    except Exception:
        bg["userOffsetX"] = 0.0
    try:
        bg["userOffsetY"] = float(bg.get("userOffsetY", 0.0) or 0.0)
    except Exception:
        bg["userOffsetY"] = 0.0

    ls = out["logoSettings"]
    ls["enabled"] = bool(ls.get("enabled", True))
    if not isinstance(ls.get("size"), (int, float)):
        ls["size"] = 200
    ls["size"] = float(max(100, min(1000, float(ls.get("size", 200)))))
    ls["reactivity"] = float(max(0.0, min(2.0, float(ls.get("reactivity", 0.5)))))
    ls["smoothing"] = float(max(0.0, min(0.99, float(ls.get("smoothing", 0.75)))))
    ls["spinEnabled"] = bool(ls.get("spinEnabled", False))
    ls["spinDirection"] = str(ls.get("spinDirection", "cw") or "cw").strip().lower()
    if ls["spinDirection"] not in ("cw", "ccw"):
        ls["spinDirection"] = "cw"
    try:
        ls["spinSpeed"] = float(ls.get("spinSpeed", 0.0) or 0.0)
    except Exception:
        ls["spinSpeed"] = 0.0
    ls["spinSpeed"] = float(max(0.0, min(720.0, float(ls.get("spinSpeed", 0.0) or 0.0))))

    pb = out["previewBindings"]
    pb["spectrumAttachToLogo"] = bool(pb.get("spectrumAttachToLogo", True))
    try:
        pb["spectrumLogoGap"] = float(pb.get("spectrumLogoGap", 0.0) or 0.0)
    except Exception:
        pb["spectrumLogoGap"] = 0.0
    pb["spectrumLogoGap"] = float(max(0.0, min(500.0, pb["spectrumLogoGap"])))

    out["spectrumEnabled"] = bool(out.get("spectrumEnabled", True))

    effects = out.get("effects") if _is_obj(out.get("effects")) else {}
    vignette_in = effects.get("vignette") if _is_obj(effects.get("vignette")) else {}
    smoke_in = effects.get("smoke") if _is_obj(effects.get("smoke")) else {}
    effects["vignette"] = {
        **(base.get("effects", {}).get("vignette", {}) if _is_obj(base.get("effects")) else {}),
        **vignette_in,
        "enabled": bool(vignette_in.get("enabled", False)),
        "strength": float(max(0.0, min(1.0, float(vignette_in.get("strength", 0.35) or 0.35)))),
        "feather": float(max(0.0, min(1.0, float(vignette_in.get("feather", 0.65) or 0.65)))),
        "color": str(vignette_in.get("color", "#000000") or "#000000"),
        "opacity": float(max(0.0, min(1.0, float(vignette_in.get("opacity", 0.65) or 0.65)))),
        "reactivity": float(max(0.0, min(5.0, float(vignette_in.get("reactivity", 0.0) or 0.0)))),
    }
    effects["smoke"] = {
        **(base.get("effects", {}).get("smoke", {}) if _is_obj(base.get("effects")) else {}),
        **smoke_in,
        "enabled": bool(smoke_in.get("enabled", False)),
        "strength": float(max(0.0, min(1.0, float(smoke_in.get("strength", 0.35) or 0.35)))),
        "blur": float(max(0.0, min(1.0, float(smoke_in.get("blur", 0.55) or 0.55)))),
        "noise": float(max(0.0, min(1.0, float(smoke_in.get("noise", 0.55) or 0.55)))),
        "speed": float(max(0.0, min(2.0, float(smoke_in.get("speed", 0.35) or 0.35)))),
        "color": str(smoke_in.get("color", "#000000") or "#000000"),
        "opacity": float(max(0.0, min(1.0, float(smoke_in.get("opacity", 0.55) or 0.55)))),
    }
    out["effects"] = effects

    out["lightningEnabled"] = bool(out.get("lightningEnabled", True))
    try:
        from features.video.lib.lightning_style_registry import normalize_lightning_layers

        out["lightningLayers"] = normalize_lightning_layers(out.get("lightningLayers"))
    except Exception:
        out["lightningLayers"] = list(base.get("lightningLayers") or [])

    overlays_in = input_template.get("textOverlays") if isinstance(input_template.get("textOverlays"), list) else []
    overlays: list[dict] = []
    for raw in overlays_in:
        if not _is_obj(raw):
            continue
        anim = str(raw.get("animation", "fade") or "fade")
        if anim not in ("fade", "slide_up", "slide_down", "slide_left", "slide_right", "pop", "typewriter", "glow", "shake", "none"):
            anim = "fade"
        anchor = str(raw.get("anchor", "top-left") or "top-left").lower().strip()
        # Accept domain shorthand (left/top) and full corners used by title lists.
        if anchor not in (
            "top-left",
            "top",
            "top-center",
            "top-right",
            "left",
            "center",
            "right",
            "bottom-left",
            "bottom",
            "bottom-center",
            "bottom-right",
        ):
            anchor = "top-left"
        fill_mode = str(raw.get("fillMode", "solid") or "solid").lower().strip()
        if fill_mode not in ("solid", "gradient", "neon"):
            fill_mode = "solid"
        gradient_direction = str(raw.get("gradientDirection", "vertical") or "vertical").lower().strip()
        if gradient_direction not in ("vertical", "horizontal", "diagonal"):
            gradient_direction = "vertical"
        gradient_raw = raw.get("gradientColors")
        gradient_colors = (
            [str(c) for c in gradient_raw if str(c or "").strip()]
            if isinstance(gradient_raw, list)
            else []
        )[:5]
        glow_grad_raw = raw.get("glowGradientColors")
        overlay = {
            "enabled": bool(raw.get("enabled", False)),
            "text": str(raw.get("text", "") or "").strip(),
            "startSec": float(max(0.0, min(36000.0, float(raw.get("startSec", 0.0) or 0.0)))),
            "durationSec": float(max(0.1, min(36000.0, float(raw.get("durationSec", 3.0) or 3.0)))),
            "anchor": anchor,
            "x": float(max(-2000.0, min(2000.0, float(raw.get("x", 24.0) if "x" in raw else 24.0)))),
            "y": float(max(-2000.0, min(2000.0, float(raw.get("y", 24.0) if "y" in raw else 24.0)))),
            "sizePx": float(max(8.0, min(320.0, float(raw.get("sizePx", raw.get("fontSize", 46.0)) or 46.0)))),
            "color": str(raw.get("color", "#ffffff") or "#ffffff"),
            "fillMode": fill_mode,
            "gradientColors": gradient_colors,
            "gradientDirection": gradient_direction,
            "glowColor": str(raw.get("glowColor", "#ff4fd8") or "#ff4fd8"),
            "glowMode": str(raw.get("glowMode", "solid") or "solid"),
            "glowGradientColors": (
                [str(c) for c in glow_grad_raw if c][:5]
                if isinstance(glow_grad_raw, list)
                else []
            ),
            "glowGradientDirection": str(
                raw.get("glowGradientDirection", "horizontal") or "horizontal"
            ),
            "strokeColor": str(raw.get("strokeColor", "#000000") or "#000000"),
            "strokeWidth": float(max(0.0, min(12.0, float(raw.get("strokeWidth", 2.0) if "strokeWidth" in raw else 2.0)))),
            "shadow": float(max(0.0, min(1.0, float(raw.get("shadow", 0.4) if "shadow" in raw else 0.4)))),
            "shadowBlur": float(max(0.0, min(40.0, float(raw.get("shadowBlur", 0.0) if "shadowBlur" in raw else 0.0)))),
            "glow": float(max(0.0, min(1.0, float(raw.get("glow", 0.0) if "glow" in raw else 0.0)))),
            "glowBlur": float(max(0.0, min(48.0, float(raw.get("glowBlur", 8.0) if "glowBlur" in raw else 8.0)))),
            "extrudeDepth": float(max(0.0, min(24.0, float(raw.get("extrudeDepth", 0.0) if "extrudeDepth" in raw else 0.0)))),
            "extrudeColor": str(raw.get("extrudeColor", "#1a1a1a") or "#1a1a1a"),
            "animation": anim,
            "fontFamily": str(raw.get("fontFamily", "arial") or "arial"),
            "bold": bool(raw.get("bold", False)),
            "italic": bool(raw.get("italic", False)),
            "opacity": float(max(0.0, min(1.0, float(raw.get("opacity", 1.0) if "opacity" in raw else 1.0)))),
            "letterSpacing": float(raw.get("letterSpacing", 0.0) or 0.0),
            "lineSpacing": float(raw.get("lineSpacing", 1.15) or 1.15),
        }
        # Keep domain tag so preview can hide GPU twins while Qt overlay edits.
        source = str(raw.get("source") or "").strip()
        if source:
            overlay["source"] = source
        overlays.append(overlay)
    out["textOverlays"] = overlays

    from features.video.lib.video_template_draft import normalize_spectrum_preset_key

    style = normalize_spectrum_preset_key(str(out.get("style", "orbit-spikes") or ""))
    out["style"] = style or "orbit-spikes"

    raw_layers = input_template.get("layers") if isinstance(input_template.get("layers"), list) else []
    fallback_layer = base["layers"][0]
    layers_src = raw_layers if raw_layers else [fallback_layer]
    out_layers: list[dict] = []
    for i, layer in enumerate(layers_src):
        layer_in = layer if _is_obj(layer) else {}
        curved = layer_in.get("curved")
        if not isinstance(curved, bool):
            curved = bool(fallback_layer.get("curved", True))
        mirrored = layer_in.get("mirrored")
        if not isinstance(mirrored, bool):
            mirrored = bool(fallback_layer.get("mirrored", True))

        bar_width = layer_in.get("barWidth")
        if not isinstance(bar_width, (int, float)):
            bar_width = fallback_layer.get("barWidth", 4)
        bar_count = layer_in.get("barCount")
        if not isinstance(bar_count, (int, float)):
            bar_count = fallback_layer.get("barCount", 64)

        fill_circle = layer_in.get("fillCircle")
        if not isinstance(fill_circle, bool):
            fill_circle = bool(fallback_layer.get("fillCircle", False))
        solid_band = layer_in.get("solidBand")
        if not isinstance(solid_band, bool):
            solid_band = bool(fallback_layer.get("solidBand", False))

        thickness = layer_in.get("thickness")
        if not isinstance(thickness, (int, float)) and isinstance(layer_in.get("strength"), (int, float)):
            thickness = float(layer_in.get("strength", 0)) * float(layer_in.get("reactivity", 1))
        if not isinstance(thickness, (int, float)):
            thickness = fallback_layer.get("thickness", 150)
        thickness_clamped = float(max(1, min(600, float(thickness))))

        gravity = str(layer_in.get("gravity", fallback_layer.get("gravity", "top")))
        if gravity == "normal":
            gravity = "top"
        g_low = gravity.lower().strip()
        if g_low in ("outside", "out", "radial-out", "radial_out"):
            gravity = "outward"
        elif g_low in ("inside", "in", "radial-in", "radial_in"):
            gravity = "inward"
        elif g_low in ("top", "bottom", "left", "right", "outward", "inward"):
            gravity = g_low
        else:
            gravity = str(fallback_layer.get("gravity", "top"))
            if gravity == "normal":
                gravity = "top"
            g_fb = gravity.lower().strip()
            if g_fb not in ("top", "bottom", "left", "right", "outward", "inward"):
                gravity = "top"
            else:
                gravity = g_fb

        col_in = layer_in.get("color") if _is_obj(layer_in.get("color")) else {}
        color = {**fallback_layer.get("color", {}), **col_in}
        if str(color.get("mode", "solid")) not in ("solid", "gradient"):
            color["mode"] = "solid"
        if not isinstance(color.get("solidColor"), str):
            color["solidColor"] = "#ffffff"
        if not isinstance(color.get("gradientColors"), list):
            color["gradientColors"] = ["#ff00ff", "#00ffff"]
        if not isinstance(color.get("gradientDirection"), str):
            color["gradientDirection"] = "left-to-right"

        out_layers.append(
            {
                "id": str(layer_in.get("id") or f"layer-{i+1}"),
                "name": str(layer_in.get("name") or f"Layer {i+1}"),
                "curved": curved,
                "mirrored": mirrored,
                "fillCircle": fill_circle,
                "solidBand": solid_band,
                "thickness": thickness_clamped,
                "barWidth": float(max(0.5, min(240.0, float(bar_width)))),
                "barCount": int(max(16, min(192, round(float(bar_count))))),
                "radiusOffset": float(max(0.0, min(800.0, float(layer_in.get("radiusOffset", fallback_layer.get("radiusOffset", 0)) or 0.0)))),
                "gravity": gravity,
                "color": color,
                "glow": float(max(0.0, min(100.0, float(layer_in.get("glow", fallback_layer.get("glow", 0)) or 0.0)))),
                "blur": float(max(0.0, min(30.0, float(layer_in.get("blur", fallback_layer.get("blur", 0)) or 0.0)))),
                "rotation": float(layer_in.get("rotation", fallback_layer.get("rotation", 0)) or 0),
                "blend_mode": str(layer_in.get("blend_mode", fallback_layer.get("blend_mode", "normal")) or "normal").lower(),
                "opacity": float(max(0.0, min(1.0, float(layer_in.get("opacity", fallback_layer.get("opacity", 1)) or 1)))),
                "peakCapsEnabled": bool(layer_in.get("peakCapsEnabled", fallback_layer.get("peakCapsEnabled", False))),
                "peakCapColor": str(layer_in.get("peakCapColor", fallback_layer.get("peakCapColor", "#ffffff")) or "#ffffff"),
                "peakCapGap": float(max(0.0, min(24.0, float(layer_in.get("peakCapGap", fallback_layer.get("peakCapGap", 4.0)) or 0.0)))),
                "peakCapThickness": float(max(1.0, min(16.0, float(layer_in.get("peakCapThickness", fallback_layer.get("peakCapThickness", 3.0)) or 1.0)))),
                "peakCapDecay": float(max(0.7, min(0.995, float(layer_in.get("peakCapDecay", fallback_layer.get("peakCapDecay", 0.92)) or 0.92)))),
                "reflectionEnabled": bool(
                    layer_in.get("reflectionEnabled", fallback_layer.get("reflectionEnabled", False))
                ),
                "reflectionOpacity": float(
                    max(
                        0.05,
                        min(
                            0.85,
                            float(
                                layer_in.get(
                                    "reflectionOpacity",
                                    fallback_layer.get("reflectionOpacity", 0.32),
                                )
                                or 0.32
                            ),
                        ),
                    )
                ),
                "pathMode": _normalize_layer_path_mode(
                    layer_in.get("pathMode", fallback_layer.get("pathMode", "auto"))
                ),
            }
        )
    out["layers"] = out_layers

    try:
        from features.video.lib.spectrum_instance_registry import (
            migrate_legacy_spectrum_to_instances,
            mirror_spectrum_instance0_to_legacy,
            normalize_spectrum_instances,
        )

        raw_instances = input_template.get("spectrumInstances") if isinstance(input_template, dict) else None
        if isinstance(raw_instances, list) and raw_instances:
            instances = normalize_spectrum_instances(raw_instances, template=out)
        else:
            # Ensure out has layers/style/position for migrate wrap.
            instances = migrate_legacy_spectrum_to_instances(out)
        # Heal empty primary rings from normalized top-level layers (never wipe a good stack).
        if instances and out_layers:
            primary_layers = instances[0].get("layers") if isinstance(instances[0], dict) else None
            if not (isinstance(primary_layers, list) and primary_layers):
                instances[0]["layers"] = list(out_layers)
        mirror_spectrum_instance0_to_legacy(out, instances)
    except Exception:
        out.setdefault("spectrumInstances", [])

    return out


def template_to_json_str(template: dict) -> str:
    return json.dumps(template, ensure_ascii=False)
