from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


def default_template() -> dict:
    return {
        "templateName": "New Template",
        "style": "classic-vertical",
        "logoPath": "",
        "spectrumEnabled": True,
        "layers": [
            {
                "id": "base-layer",
                "name": "Base Ring",
                "curved": True,
                "mirrored": True,
                "fillCircle": False,
                "thickness": 30,
                "barWidth": 4,
                "radiusOffset": 0,
                "gravity": "bottom",
                "color": {
                    "mode": "solid",
                    "solidColor": "#ffffff",
                    "gradientColors": ["#ff00ff", "#00ffff"],
                    "gradientDirection": "left-to-right",
                },
                "glow": 0,
                "blur": 0,
                "rotation": 0,
                "blend_mode": "normal",
                "opacity": 1,
            }
        ],
        "globalColor": {
            "mode": "solid",
            "solidColor": "#ffffff",
            "gradientColors": ["#ff00ff", "#00ffff"],
            "gradientDirection": "left-to-right",
        },
        "position": {"anchor": "center", "x": 0, "y": 0},
        "renderBaseHeight": 450,
        "audioSettings": {"sensitivity": 1.0, "smoothing": 0.8, "bounce": 0, "minHeight": 0.1, "peakHold": 0},
        "backgroundSettings": {
            "brightness": 1.0,
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
        },
        "effects": {
            "vignette": {"enabled": False, "strength": 0.35, "feather": 0.65, "color": "#000000", "opacity": 0.65},
            "smoke": {"enabled": False, "strength": 0.35, "blur": 0.55, "noise": 0.55, "speed": 0.35, "color": "#000000", "opacity": 0.55},
        },
        "textOverlays": [],
    }


def _is_obj(x: Any) -> bool:
    return isinstance(x, dict)


def normalize_template(input_template: Any) -> dict:
    base = default_template()
    if not _is_obj(input_template):
        return copy.deepcopy(base)

    out = copy.deepcopy(base)
    out.update({k: v for k, v in input_template.items() if k in out or k in ("previewBackground", "previewLogo")})

    pos_in = input_template.get("position") if _is_obj(input_template.get("position")) else {}
    out["position"] = {**base["position"], **pos_in}

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
    if not isinstance(ps.get("maxCount"), (int, float)) and isinstance(ps.get("count"), (int, float)):
        ps["maxCount"] = ps.get("count")
    if not isinstance(ps.get("spawnRate"), (int, float)) and isinstance(ps.get("spawn_rate"), (int, float)):
        ps["spawnRate"] = ps.get("spawn_rate")
    if not isinstance(ps.get("lifetimeSec"), (int, float)) and isinstance(ps.get("lifetime_sec"), (int, float)):
        ps["lifetimeSec"] = ps.get("lifetime_sec")
    if not isinstance(ps.get("opacity"), (int, float)) and isinstance(ps.get("alpha"), (int, float)):
        ps["opacity"] = ps.get("alpha")

    ps["speed"] = float(max(1, min(15, float(ps.get("speed", 1)))))
    ps["reactivity"] = float(max(0.1, min(0.5, float(ps.get("reactivity", 0.1)))))
    ps["smoothing"] = float(max(0.0, min(0.99, float(ps.get("smoothing", 0.65)))))
    ps["opacity"] = float(max(0.0, min(1.0, float(ps.get("opacity", 0.35)))))
    ps["maxCount"] = int(max(200, min(2000, int(ps.get("maxCount", 200)))))
    ps["spawnRate"] = float(max(100, min(1000, float(ps.get("spawnRate", 100)))))
    ps["spawnMode"] = "reactiveOnly" if str(ps.get("spawnMode", "always")) == "reactiveOnly" else "always"
    ps["spawnTrigger"] = str(ps.get("spawnTrigger", "both"))
    if ps["spawnTrigger"] not in ("kick", "bass", "both"):
        ps["spawnTrigger"] = "both"
    ps["spawnThreshold"] = float(max(0.0, min(1.0, float(ps.get("spawnThreshold", 0.15) or 0.15))))
    ps["reactColor"] = str(ps.get("reactColor", "#ffffff") or "#ffffff")
    ps["reactStrength"] = float(max(0.0, min(1.0, float(ps.get("reactStrength", 0.65) or 0.65))))
    ps["sizeJitter"] = float(max(0.0, min(1.0, float(ps.get("sizeJitter", 0.0) or 0.0))))
    ps["drift"] = float(max(0.0, min(1.0, float(ps.get("drift", 0.0) or 0.0))))
    ps["swirl"] = float(max(0.0, min(1.0, float(ps.get("swirl", 0.0) or 0.0))))
    ps["spawnArea"] = str(ps.get("spawnArea", "centerRing") or "centerRing")
    if ps["spawnArea"] not in ("centerRing", "bottom", "edges", "full"):
        ps["spawnArea"] = "centerRing"
    ps["variant"] = str(ps.get("variant", "classic") or "classic")
    if ps["variant"] not in ("classic", "bokeh", "soap", "dust"):
        ps["variant"] = "classic"
    ps["style"] = str(ps.get("style", "dot"))
    if ps["style"] not in ("dot", "glow", "ring", "spark", "bokeh"):
        ps["style"] = "dot"

    bg = out["backgroundSettings"]
    bg["brightness"] = float(max(0.0, min(3.0, float(bg.get("brightness", 1.0)))))
    bg["reactivity"] = float(max(0.0, min(2.0, float(bg.get("reactivity", 0.0)))))
    bg["smoothing"] = float(max(0.0, min(0.99, float(bg.get("smoothing", 0.8)))))
    bg["motionMode"] = str(bg.get("motionMode", "none") or "none")
    if bg["motionMode"] not in ("none", "zoom", "vibrate", "both"):
        bg["motionMode"] = "none"
    bg["motionZoomStrength"] = float(max(0.0, min(2.0, float(bg.get("motionZoomStrength", 1.0) or 1.0))))
    bg["motionVibrateStrength"] = float(max(0.0, min(2.0, float(bg.get("motionVibrateStrength", 1.0) or 1.0))))
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

    overlays_in = input_template.get("textOverlays") if isinstance(input_template.get("textOverlays"), list) else []
    overlays: list[dict] = []
    for raw in overlays_in[:5]:
        if not _is_obj(raw):
            continue
        anim = str(raw.get("animation", "fade") or "fade")
        if anim not in ("fade", "slide_up", "slide_down", "slide_left", "slide_right", "pop", "typewriter", "glow", "shake", "none"):
            anim = "fade"
        anchor = str(raw.get("anchor", "top-left") or "top-left")
        if anchor not in ("top-left", "top-center", "top-right", "center", "bottom-left", "bottom-center", "bottom-right"):
            anchor = "top-left"
        overlays.append(
            {
                "enabled": bool(raw.get("enabled", False)),
                "text": str(raw.get("text", "") or "").strip(),
                "startSec": float(max(0.0, min(36000.0, float(raw.get("startSec", 0.0) or 0.0)))),
                "durationSec": float(max(0.1, min(36000.0, float(raw.get("durationSec", 3.0) or 3.0)))),
                "anchor": anchor,
                "x": float(max(-2000.0, min(2000.0, float(raw.get("x", 24.0) if "x" in raw else 24.0)))),
                "y": float(max(-2000.0, min(2000.0, float(raw.get("y", 24.0) if "y" in raw else 24.0)))),
                "sizePx": float(max(8.0, min(320.0, float(raw.get("sizePx", 46.0) if "sizePx" in raw else 46.0)))),
                "color": str(raw.get("color", "#ffffff") or "#ffffff"),
                "strokeColor": str(raw.get("strokeColor", "#000000") or "#000000"),
                "strokeWidth": float(max(0.0, min(12.0, float(raw.get("strokeWidth", 2.0) if "strokeWidth" in raw else 2.0)))),
                "shadow": float(max(0.0, min(1.0, float(raw.get("shadow", 0.4) if "shadow" in raw else 0.4)))),
                "animation": anim,
            }
        )
    out["textOverlays"] = overlays

    style = str(out.get("style", "classic-vertical") or "").strip().lower()
    if style == "symmetrical":
        style = "symmetrical-bars"
    out["style"] = style or "classic-vertical"

    raw_layers = input_template.get("layers") if isinstance(input_template.get("layers"), list) else []
    fallback_layer = base["layers"][0]
    layers_src = raw_layers if raw_layers else [fallback_layer]
    out_layers: list[dict] = []
    for i, l in enumerate(layers_src):
        layer_in = l if _is_obj(l) else {}
        curved = layer_in.get("curved")
        if not isinstance(curved, bool):
            curved = bool(fallback_layer.get("curved", True))
        mirrored = layer_in.get("mirrored")
        if not isinstance(mirrored, bool):
            mirrored = bool(fallback_layer.get("mirrored", True))

        bar_width = layer_in.get("barWidth")
        if not isinstance(bar_width, (int, float)):
            bar_width = fallback_layer.get("barWidth", 4)

        fill_circle = layer_in.get("fillCircle")
        if not isinstance(fill_circle, bool):
            fill_circle = bool(fallback_layer.get("fillCircle", False))

        thickness = layer_in.get("thickness")
        if not isinstance(thickness, (int, float)) and isinstance(layer_in.get("strength"), (int, float)):
            thickness = float(layer_in.get("strength", 0)) * float(layer_in.get("reactivity", 1))
        if not isinstance(thickness, (int, float)):
            thickness = fallback_layer.get("thickness", 150)
        thickness_clamped = float(max(1, min(120, float(thickness))))

        gravity = str(layer_in.get("gravity", fallback_layer.get("gravity", "bottom")))
        if gravity not in ("bottom", "top", "left", "right"):
            gravity = str(fallback_layer.get("gravity", "bottom"))

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
                "thickness": thickness_clamped,
                "barWidth": float(bar_width),
                "radiusOffset": float(max(0.0, min(400.0, float(layer_in.get("radiusOffset", fallback_layer.get("radiusOffset", 0)) or 0.0)))),
                "gravity": gravity,
                "color": color,
                "glow": float(max(0.0, min(100.0, float(layer_in.get("glow", fallback_layer.get("glow", 0)) or 0.0)))),
                "blur": float(max(0.0, min(30.0, float(layer_in.get("blur", fallback_layer.get("blur", 0)) or 0.0)))),
                "rotation": float(layer_in.get("rotation", fallback_layer.get("rotation", 0)) or 0),
                "blend_mode": str(layer_in.get("blend_mode", fallback_layer.get("blend_mode", "normal")) or "normal").lower(),
                "opacity": float(max(0.0, min(1.0, float(layer_in.get("opacity", fallback_layer.get("opacity", 1)) or 1)))),
            }
        )
    out["layers"] = out_layers
    return out


def template_to_json_str(tpl: dict) -> str:
    return json.dumps(tpl, ensure_ascii=False)


@dataclass(frozen=True)
class VideoTemplate:
    id: str
    name: str
    source: str
    template: dict
    updated_at: str
