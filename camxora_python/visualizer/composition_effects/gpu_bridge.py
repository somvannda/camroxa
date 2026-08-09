"""Bridge composition compiler output → GPU preview/export template keys.

The engine emits ``lightingSettings`` / ``cameraSettings`` / ``atmosphereSettings``.
The live GPU path still consumes legacy keys (``lightningEnabled``,
``effects.camera_shake``, ``backgroundSettings.motionMode``, …). This module
is the single place that maps between them so Studio preview and export stay
engine-true without forking Video inspectors.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from visualizer.scene import NONE

# Composition lighting effect → GPU lightning style.
_LIGHTING_STYLE: dict[str, str] = {
    "lightning": "fork",
    "strobe_flash": "sheet",
    "energy_pulse": "pulse",
    "aura": "neon",
    "glow": "pulse",
    "god_rays": "ribbon",
    "lens_flare": "neon",
    "light_beam": "arc",
    "light_sweep": "horizon",
    "neon_rim": "neon",
    "halo": "pulse",
    "rim_light": "arc",
    "spot_cone": "fork",
    "volumetric_shaft": "ribbon",
    "color_wash": "sheet",
}

# Composition bus trigger → GPU lightning trigger.
_LIGHTING_TRIGGER: dict[str, str] = {
    "bass": "bass",
    "kick": "kick",
    "treble": "audio",
    "overall_loudness": "audio",
    "vocals": "audio",
    "melody": "beat",
    "snare": "kick",
    "none": "always",
}

# Evaluator legacyMotionMode → GPU motionMode whitelist.
_GPU_MOTION: dict[str, str] = {
    "none": "none",
    "zoom": "zoom",
    "pan": "vibrate",
    "rotate": "both",
    "vibrate": "vibrate",
    "both": "both",
}

# Atmosphere → soft whole-frame proxies (true weather particles are not GPU-wired yet).
_ATMOSPHERE_PROXIES: dict[str, dict[str, dict[str, Any]]] = {
    "fog": {
        "soft_diffusion": {"enabled": True, "amount": 0.4},
        "vignette": {"enabled": True, "amount": 0.28},
    },
    "mist": {"soft_diffusion": {"enabled": True, "amount": 0.25}},
    "haze": {"soft_diffusion": {"enabled": True, "amount": 0.2}},
    "smoke": {
        "soft_diffusion": {"enabled": True, "amount": 0.35},
        "vignette": {"enabled": True, "amount": 0.35},
    },
    "dust": {"film_grain": {"enabled": True, "amount": 0.22}},
    "rain": {"film_grain": {"enabled": True, "amount": 0.18}},
    "snow": {"soft_diffusion": {"enabled": True, "amount": 0.22}},
    "storm": {
        "vignette": {"enabled": True, "amount": 0.4},
        "contrast": {"enabled": True, "amount": 0.2},
    },
    "stars": {"film_grain": {"enabled": True, "amount": 0.12}},
    "nebula": {
        "bloom": {"enabled": True, "amount": 0.35},
        "saturation": {"enabled": True, "amount": 0.15},
    },
    "aurora": {
        "bloom": {"enabled": True, "amount": 0.3},
        "chromatic_aberration": {"enabled": True, "amount": 0.15},
    },
    "underwater": {
        "soft_diffusion": {"enabled": True, "amount": 0.3},
        "color_grading": {"enabled": True, "amount": 0.35},
    },
    "void": {"vignette": {"enabled": True, "amount": 0.55}},
    "heatwave": {"lens_distortion": {"enabled": True, "amount": 0.2}},
    "clouds": {"soft_diffusion": {"enabled": True, "amount": 0.18}},
}


def _merge_effect(effects: dict[str, Any], key: str, payload: dict[str, Any]) -> None:
    existing = effects.get(key) if isinstance(effects.get(key), dict) else None
    if existing and bool(existing.get("enabled")):
        return
    effects[key] = dict(payload)


def apply_gpu_preview_bridge(
    rendered: dict[str, Any],
    *,
    source_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enrich a compiled renderer dict for VideoSpectrumPreview / export GPU."""
    if not isinstance(rendered, dict):
        return {}
    out = deepcopy(rendered)
    effects = out.get("effects") if isinstance(out.get("effects"), dict) else {}
    effects = dict(effects)

    # --- Background motion (GPU only accepts none/zoom/vibrate/both) ---
    bg = out.get("backgroundSettings") if isinstance(out.get("backgroundSettings"), dict) else {}
    bg = dict(bg)
    legacy = str(bg.get("motionMode") or "none")
    evaluated = bg.get("evaluated") if isinstance(bg.get("evaluated"), dict) else {}
    if legacy not in _GPU_MOTION:
        legacy = str(evaluated.get("legacyMotionMode") or "none")
    motion_id = str(bg.get("motionId") or evaluated.get("motionId") or "static")
    gpu_mode = _GPU_MOTION.get(legacy)
    if gpu_mode is None:
        gpu_mode = "none" if motion_id in ("", "static", NONE) else "zoom"
    bg["motionMode"] = gpu_mode
    bg["enabled"] = True
    if evaluated.get("scale") is not None:
        try:
            scale = float(evaluated.get("scale") or 1.0)
            bg["motionZoomStrength"] = max(0.5, min(8.0, abs(scale - 1.0) * 40.0 + 1.0))
        except (TypeError, ValueError):
            pass
    assets = out.get("assets") if isinstance(out.get("assets"), dict) else {}
    path = str(bg.get("path") or assets.get("backgroundImage") or out.get("previewBackground") or "").strip()
    if path:
        bg["path"] = path
        out["previewBackground"] = path
    out["backgroundSettings"] = bg

    # --- Logo path + defaults ---
    logo_path = str(
        out.get("logoPath") or assets.get("logo") or out.get("previewLogo") or ""
    ).strip()
    ls = out.get("logoSettings") if isinstance(out.get("logoSettings"), dict) else {}
    ls = dict(ls)
    if logo_path:
        out["logoPath"] = logo_path
        out["previewLogo"] = logo_path
    ls.setdefault("size", 192.0)
    ls.setdefault("scale", 1.0)
    ls.setdefault("opacity", 1.0)
    ls.setdefault("circleMask", True)
    out["logoSettings"] = ls

    # --- Camera → effects.camera_shake ---
    camera = out.get("cameraSettings") if isinstance(out.get("cameraSettings"), dict) else {}
    behavior = str(camera.get("behaviorId") or NONE)
    shake_amt = float(camera.get("shake") or 0.0)
    shake_behaviors = {"shake", "handheld", "whip_pan", "punch_in"}
    if bool(camera.get("enabled")) and (behavior in shake_behaviors or shake_amt > 0.0):
        intensity = 8.0 + max(0.0, shake_amt) * 120.0
        if behavior == "handheld":
            intensity = max(intensity, 6.0)
        _merge_effect(
            effects,
            "camera_shake",
            {"enabled": True, "intensity": float(min(24.0, intensity)), "smoothing": 0.85},
        )

    # --- Lighting → lightningEnabled / lightningLayers ---
    lighting = out.get("lightingSettings") if isinstance(out.get("lightingSettings"), dict) else {}
    effect_id = str(lighting.get("effectId") or NONE)
    if bool(lighting.get("enabled")) and effect_id not in ("", NONE, "none"):
        style = _LIGHTING_STYLE.get(effect_id, "fork")
        trigger_id = str(lighting.get("triggerId") or "bass")
        trigger = _LIGHTING_TRIGGER.get(trigger_id, "bass")
        color = str(lighting.get("color") or "#e0f2fe")
        draw = lighting.get("draw") if isinstance(lighting.get("draw"), dict) else {}
        intensity = float(draw.get("intensity") or 0.85)
        out["lightningEnabled"] = True
        out["lightningLayers"] = [
            {
                "id": "composition-lighting-1",
                "name": effect_id.replace("_", " ").title(),
                "enabled": True,
                "style": style,
                "spawnMode": "fixed",
                "x": 0.0,
                "y": -80.0,
                "direction": "down",
                "rotation": 0.0,
                "color": {
                    "mode": "gradient",
                    "solidColor": color,
                    "gradientColors": [color, "#ffffff", color],
                },
                "opacity": 0.9,
                "intensity": max(0.35, min(1.0, intensity)),
                "reactivity": 0.65,
                "speed": 1.0,
                "reactMotionSpeed": 1.0,
                "flashRate": 0.85,
                "thickness": 2.8,
                "taper": 0.65,
                "glow": 0.55,
                "branchiness": 0.4,
                "blend": "add",
                "length": 220.0,
                "lengthReactivity": 0.2,
                "trigger": trigger,
                "triggerThreshold": 0.18,
                "seed": 1.0,
                "seedLock": False,
            }
        ]
        # Soft glow for non-bolt lighting looks.
        if effect_id in {"aura", "glow", "halo", "neon_rim", "color_wash"}:
            _merge_effect(effects, "glow", {"enabled": True, "amount": 0.35})
            _merge_effect(effects, "bloom", {"enabled": True, "amount": 0.3})
    else:
        out.setdefault("lightningEnabled", False)

    # --- Atmosphere proxies (additive; do not clobber explicit post) ---
    atmosphere = out.get("atmosphereSettings") if isinstance(out.get("atmosphereSettings"), dict) else {}
    atm_id = str(atmosphere.get("atmosphereId") or NONE)
    if bool(atmosphere.get("enabled")) and atm_id not in ("", NONE, "none"):
        for key, payload in _ATMOSPHERE_PROXIES.get(atm_id, {}).items():
            _merge_effect(effects, key, payload)

    out["effects"] = effects

    # --- Studio extras from source document ---
    src = source_doc if isinstance(source_doc, dict) else {}
    bindings = out.get("previewBindings") if isinstance(out.get("previewBindings"), dict) else {}
    bindings = dict(bindings)
    if "spectrumAttachToLogo" in src:
        bindings["spectrumAttachToLogo"] = bool(src.get("spectrumAttachToLogo"))
    out["previewBindings"] = bindings

    if src.get("albumEnabled") or src.get("titleEnabled") or src.get("albumManualText") or src.get("titleManualText"):
        out["albumText"] = {
            "enabled": bool(src.get("albumEnabled")),
            "text": str(src.get("albumManualText") or ""),
        }
        out["titleText"] = {
            "enabled": bool(src.get("titleEnabled")),
            "text": str(src.get("titleManualText") or ""),
        }

    return out
