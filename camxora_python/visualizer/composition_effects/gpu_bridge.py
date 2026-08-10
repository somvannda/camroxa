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

from visualizer.composition_effects.atmosphere_gpu import build_atmosphere_draw
from visualizer.scene import NONE

# Composition lighting effect → GPU lightning style + unique bolt profile.
# Styles may share GPU enums; thickness/glow/branchiness/length keep looks distinct.
_LIGHTING_PROFILES: dict[str, dict[str, Any]] = {
    "lightning": {"style": "fork", "thickness": 3.2, "glow": 0.7, "branchiness": 0.75, "length": 260.0, "flashRate": 0.95},
    "strobe_flash": {"style": "sheet", "thickness": 5.5, "glow": 0.9, "branchiness": 0.1, "length": 180.0, "flashRate": 1.6},
    "energy_pulse": {"style": "pulse", "thickness": 2.4, "glow": 0.85, "branchiness": 0.25, "length": 200.0, "flashRate": 1.1},
    "aura": {"style": "neon", "thickness": 4.8, "glow": 0.95, "branchiness": 0.15, "length": 140.0, "flashRate": 0.45},
    "glow": {"style": "pulse", "thickness": 6.0, "glow": 1.0, "branchiness": 0.05, "length": 120.0, "flashRate": 0.35},
    "god_rays": {"style": "ribbon", "thickness": 2.0, "glow": 0.65, "branchiness": 0.35, "length": 320.0, "flashRate": 0.55},
    "lens_flare": {"style": "neon", "thickness": 1.6, "glow": 1.0, "branchiness": 0.05, "length": 90.0, "flashRate": 0.8},
    "light_beam": {"style": "arc", "thickness": 2.8, "glow": 0.6, "branchiness": 0.2, "length": 280.0, "flashRate": 0.5},
    "light_sweep": {"style": "horizon", "thickness": 3.6, "glow": 0.55, "branchiness": 0.1, "length": 240.0, "flashRate": 0.7},
    "neon_rim": {"style": "neon", "thickness": 1.8, "glow": 0.8, "branchiness": 0.12, "length": 160.0, "flashRate": 0.4},
    "halo": {"style": "pulse", "thickness": 7.0, "glow": 0.75, "branchiness": 0.08, "length": 100.0, "flashRate": 0.3},
    "rim_light": {"style": "arc", "thickness": 1.4, "glow": 0.5, "branchiness": 0.18, "length": 190.0, "flashRate": 0.6},
    "spot_cone": {"style": "fork", "thickness": 4.2, "glow": 0.45, "branchiness": 0.3, "length": 210.0, "flashRate": 0.5},
    "volumetric_shaft": {"style": "ribbon", "thickness": 5.0, "glow": 0.7, "branchiness": 0.22, "length": 340.0, "flashRate": 0.4},
    "color_wash": {"style": "sheet", "thickness": 8.0, "glow": 0.4, "branchiness": 0.0, "length": 150.0, "flashRate": 0.25},
}

# Composition bus trigger → GPU lightning trigger (+ threshold bias for uniqueness).
_LIGHTING_TRIGGER: dict[str, tuple[str, float]] = {
    "bass": ("bass", 0.16),
    "kick": ("kick", 0.22),
    "treble": ("audio", 0.14),
    "overall_loudness": ("audio", 0.28),
    "vocals": ("audio", 0.2),
    "melody": ("beat", 0.18),
    "beat": ("beat", 0.12),
    "snare": ("kick", 0.32),
    "none": ("always", 0.0),
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

# Atmosphere → light secondary grade only (primary look is atmosphereDraw geometry).
_ATMOSPHERE_PROXIES: dict[str, dict[str, dict[str, Any]]] = {
    "fog": {"soft_diffusion": {"enabled": True, "amount": 0.12}},
    "mist": {"soft_diffusion": {"enabled": True, "amount": 0.08}},
    "haze": {"soft_diffusion": {"enabled": True, "amount": 0.07}},
    "smoke": {"vignette": {"enabled": True, "amount": 0.14}},
    "dust": {"film_grain": {"enabled": True, "amount": 0.08}},
    "rain": {},
    "snow": {},
    "storm": {"contrast": {"enabled": True, "amount": 0.1}},
    "stars": {},
    "nebula": {"bloom": {"enabled": True, "amount": 0.12}},
    "aurora": {"bloom": {"enabled": True, "amount": 0.1}},
    "underwater": {"color_grading": {"enabled": True, "amount": 0.12}},
    "void": {"vignette": {"enabled": True, "amount": 0.22}},
    "heatwave": {"lens_distortion": {"enabled": True, "amount": 0.12}},
    "clouds": {},
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
            zoom_boost = float(evaluated.get("zoomStrength") or 1.0)
            bg["motionZoomStrength"] = max(
                0.5, min(8.0, (abs(scale - 1.0) * 40.0 + 1.0) * max(0.5, zoom_boost))
            )
            bg["userScale"] = max(0.85, min(1.45, scale))
        except (TypeError, ValueError):
            pass
    if evaluated.get("offsetX") is not None or evaluated.get("offsetY") is not None:
        try:
            bg["userOffsetX"] = float(evaluated.get("offsetX") or 0.0) * 180.0
            bg["userOffsetY"] = float(evaluated.get("offsetY") or 0.0) * 180.0
        except (TypeError, ValueError):
            pass
    if evaluated.get("vibrateStrength") is not None:
        try:
            bg["motionVibrateStrength"] = max(
                0.2, min(8.0, float(evaluated.get("vibrateStrength") or 1.0))
            )
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
    # Do not force a circular crop on load — only mask when explicitly enabled.
    logo_comp = None
    if isinstance(out.get("composition"), dict):
        logo_comp = out["composition"].get("logo")
    src_early = source_doc if isinstance(source_doc, dict) else {}
    if not isinstance(logo_comp, dict) and isinstance(src_early.get("composition"), dict):
        logo_comp = src_early["composition"].get("logo")
    if isinstance(logo_comp, dict) and "circleMask" in logo_comp:
        ls["circleMask"] = bool(logo_comp.get("circleMask"))
    elif "circleMask" not in ls:
        ls["circleMask"] = False
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
        profile = dict(_LIGHTING_PROFILES.get(effect_id) or _LIGHTING_PROFILES["lightning"])
        trigger_id = str(lighting.get("triggerId") or "bass")
        trigger, threshold = _LIGHTING_TRIGGER.get(trigger_id, ("bass", 0.18))
        color = str(lighting.get("color") or "#e0f2fe")
        draw = lighting.get("draw") if isinstance(lighting.get("draw"), dict) else {}
        intensity = float(draw.get("intensity") or 0.85)
        # Expert overrides from lightingSettings / composition.
        thickness = float(lighting.get("thickness") or profile["thickness"])
        glow = float(lighting.get("glow") or profile["glow"])
        flash_rate = float(lighting.get("flashRate") or profile["flashRate"])
        speed = float(lighting.get("speed") or 1.0)
        out["lightningEnabled"] = True
        out["lightningLayers"] = [
            {
                "id": "composition-lighting-1",
                "name": effect_id.replace("_", " ").title(),
                "enabled": True,
                "effectId": effect_id,
                "style": str(profile["style"]),
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
                "intensity": max(0.35, min(1.5, intensity)),
                "reactivity": 0.65,
                "speed": max(0.25, min(3.0, speed)),
                "reactMotionSpeed": max(0.25, min(3.0, speed)),
                "flashRate": max(0.1, min(2.0, flash_rate)),
                "thickness": max(0.5, min(10.0, thickness)),
                "taper": 0.65,
                "glow": max(0.0, min(1.2, glow)),
                "branchiness": float(profile["branchiness"]),
                "blend": "add",
                "length": float(profile["length"]),
                "lengthReactivity": 0.2,
                "trigger": trigger,
                "triggerBus": trigger_id,
                "triggerThreshold": float(threshold),
                "seed": 1.0 + (hash(effect_id) % 97) * 0.01,
                "seedLock": False,
            }
        ]
        # Soft glow / cinematic lighting looks beyond bolt geometry (unique amounts).
        if effect_id in {"aura", "glow", "halo", "neon_rim", "color_wash", "rim_light"}:
            _merge_effect(effects, "glow", {"enabled": True, "amount": 0.25 + 0.05 * glow})
            _merge_effect(effects, "bloom", {"enabled": True, "amount": 0.2 + 0.2 * glow})
        if effect_id in {"god_rays", "volumetric_shaft", "light_beam", "light_sweep", "spot_cone"}:
            _merge_effect(effects, "bloom", {"enabled": True, "amount": 0.35 + 0.1 * intensity})
            _merge_effect(effects, "vignette", {"enabled": True, "amount": 0.18 + 0.08 * intensity})
            _merge_effect(effects, "soft_diffusion", {"enabled": True, "amount": 0.12 + 0.1 * intensity})
        if effect_id in {"lens_flare", "strobe_flash", "energy_pulse"}:
            _merge_effect(effects, "bloom", {"enabled": True, "amount": 0.45 + 0.1 * flash_rate})
            _merge_effect(effects, "chromatic_aberration", {"enabled": True, "amount": 0.12 + 0.08 * intensity})
        if effect_id == "lightning":
            _merge_effect(effects, "chromatic_aberration", {"enabled": True, "amount": 0.08})
    else:
        out.setdefault("lightningEnabled", False)

    # --- Atmosphere: GPU draw descriptor + soft post proxies ---
    atmosphere = out.get("atmosphereSettings") if isinstance(out.get("atmosphereSettings"), dict) else {}
    atm_id = str(atmosphere.get("atmosphereId") or NONE)
    atm_draw = build_atmosphere_draw(atmosphere)
    if atm_draw is not None:
        out["atmosphereDraw"] = atm_draw
        for key, payload in _ATMOSPHERE_PROXIES.get(atm_id, {}).items():
            _merge_effect(effects, key, payload)
    else:
        out.pop("atmosphereDraw", None)

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
        overlays: list[dict[str, Any]] = []
        if bool(src.get("albumEnabled")) and str(src.get("albumManualText") or "").strip():
            overlays.append(
                {
                    "enabled": True,
                    "text": str(src.get("albumManualText") or ""),
                    "anchor": "top-center",
                    "animation": "fade",
                    "startSec": 0.0,
                    "durationSec": 3600.0,
                    "overlayKind": "text",
                }
            )
        if bool(src.get("titleEnabled")) and str(src.get("titleManualText") or "").strip():
            overlays.append(
                {
                    "enabled": True,
                    "text": str(src.get("titleManualText") or ""),
                    "anchor": "bottom-center",
                    "animation": "fade",
                    "startSec": 0.0,
                    "durationSec": 3600.0,
                    "overlayKind": "text",
                }
            )
        if overlays:
            out["textOverlays"] = overlays

    # Overlay object → filmic frame overlays (Session A: ≠ Text typography).
    overlay_settings = out.get("overlaySettings") if isinstance(out.get("overlaySettings"), dict) else {}
    comp = out.get("composition") if isinstance(out.get("composition"), dict) else {}
    if not comp and isinstance(src.get("composition"), dict):
        comp = src["composition"]

    # Spectrum drag offsets → template position + primary instance coords.
    spec_pos = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
    if spec_pos:
        try:
            px = float(spec_pos.get("offsetX") or 0.0) * 480.0
            py = float(spec_pos.get("offsetY") or 0.0) * 270.0
        except (TypeError, ValueError):
            px, py = 0.0, 0.0
        pos = out.get("position") if isinstance(out.get("position"), dict) else {}
        out["position"] = {**pos, "anchor": str(pos.get("anchor") or "center"), "x": px, "y": py}
        instances = out.get("spectrumInstances")
        if isinstance(instances, list) and instances and isinstance(instances[0], dict):
            inst0 = dict(instances[0])
            inst0["x"] = px
            inst0["y"] = py
            inst0["anchor"] = "center"
            instances[0] = inst0
            out["spectrumInstances"] = instances

    overlay_amount = 0.28
    try:
        overlay_amount = float((comp.get("overlay") or {}).get("amount") or 0.28)
    except (TypeError, ValueError):
        overlay_amount = 0.28
    if bool(overlay_settings.get("enabled")):
        style = str(src.get("overlayStyle") or overlay_settings.get("style") or "film_grain")
        amt = float(overlay_amount)
        # Each style gets a unique effect signature (dust ≠ film_grain).
        if style == "film_grain":
            _merge_effect(effects, "film_grain", {"enabled": True, "amount": amt})
            _merge_effect(effects, "smoke", {"enabled": True, "blur": max(0.1, amt * 0.6), "opacity": amt * 0.7})
        elif style == "dust":
            _merge_effect(effects, "soft_diffusion", {"enabled": True, "amount": max(0.12, amt * 0.85)})
            _merge_effect(effects, "film_grain", {"enabled": True, "amount": max(0.08, amt * 0.45)})
        elif style == "vhs":
            _merge_effect(effects, "rgb_split", {"enabled": True, "amount": amt})
            _merge_effect(effects, "vignette", {"enabled": True, "amount": max(0.1, amt * 0.5)})
        elif style == "glitch":
            _merge_effect(effects, "chromatic_aberration", {"enabled": True, "amount": amt})
            _merge_effect(effects, "rgb_split", {"enabled": True, "amount": max(0.08, amt * 0.55)})
        elif style == "scanlines":
            _merge_effect(effects, "vignette", {"enabled": True, "amount": max(0.2, amt)})
            _merge_effect(effects, "contrast", {"enabled": True, "amount": max(0.1, amt * 0.4)})
        elif style == "light_leak":
            _merge_effect(effects, "bloom", {"enabled": True, "amount": amt})
            _merge_effect(effects, "saturation", {"enabled": True, "amount": max(0.08, amt * 0.35)})
        else:
            _merge_effect(effects, "film_grain", {"enabled": True, "amount": amt})
        out["overlaySettings"] = {**overlay_settings, "style": style, "amount": amt}
        out["effects"] = effects

    # --- Expert tuning → live GPU keys ---
    _apply_expert_tuning(out, comp)
    return out


def _apply_expert_tuning(out: dict[str, Any], comp: dict[str, Any]) -> None:
    if not isinstance(comp, dict):
        return
    # Palette expert — keep settings on the template (colors are baked in compile /
    # re-applied in live_motion). Avoid full-frame saturation washes that drown spectrum hue.
    try:
        raw_i = comp.get("paletteIntensity")
        raw_s = comp.get("paletteSaturation")
        pal_intensity = max(0.0, min(2.0, float(1.0 if raw_i is None else raw_i)))
        pal_sat = max(0.0, min(2.0, float(1.0 if raw_s is None else raw_s)))
    except (TypeError, ValueError):
        pal_intensity, pal_sat = 1.0, 1.0
    if comp.get("colorPalette") not in (None, "", NONE, "none"):
        out["paletteSettings"] = {
            "intensity": pal_intensity,
            "saturation": pal_sat,
            "paletteId": str(comp.get("colorPalette")),
        }

    bg_comp = comp.get("background") if isinstance(comp.get("background"), dict) else {}
    bg = out.get("backgroundSettings") if isinstance(out.get("backgroundSettings"), dict) else {}
    bg = dict(bg)
    if "brightness" in bg_comp:
        bg["brightness"] = float(bg_comp.get("brightness") or 1.0)
    if "contrast" in bg_comp:
        bg["contrast"] = float(bg_comp.get("contrast") or 1.0)
    if "reactivity" in bg_comp:
        bg["reactivity"] = float(bg_comp.get("reactivity") or 0.0)
    if "saturation" in bg_comp:
        bg["saturation"] = float(bg_comp.get("saturation") or 1.0)
    if "hue" in bg_comp:
        bg["hue"] = float(bg_comp.get("hue") or 0.0)
    if "smoothing" in bg_comp:
        bg["smoothing"] = float(bg_comp.get("smoothing") or 0.8)
    video = ""
    assets = out.get("assets") if isinstance(out.get("assets"), dict) else {}
    if isinstance(assets, dict):
        video = str(assets.get("backgroundVideo") or "").strip()
    if video:
        bg["path"] = video
        bg["sourceKind"] = "video"
        out["previewBackground"] = video
        out["backgroundVideo"] = video
    out["backgroundSettings"] = bg

    spec = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
    audio = out.get("audioSettings") if isinstance(out.get("audioSettings"), dict) else {}
    audio = dict(audio)
    # Expert bar height multiplies animation-authored height — never replaces it.
    if "barHeight" in spec:
        try:
            expert_bar = max(0.25, min(4.0, float(spec.get("barHeight") or 1.0)))
        except (TypeError, ValueError):
            expert_bar = 1.0
        base_bar = float(audio.get("barHeight") or 1.0)
        audio["barHeight"] = max(0.25, min(12.0, base_bar * expert_bar))
    audio_comp = comp.get("audio") if isinstance(comp.get("audio"), dict) else {}
    if "gain" in audio_comp:
        audio["inputGain"] = float(audio_comp.get("gain") or 1.0)
        audio["sensitivity"] = float(audio_comp.get("gain") or 1.0)
    if "smoothing" in audio_comp:
        audio["smoothing"] = float(audio_comp.get("smoothing") or 0.65)
        audio["motionSmoothing"] = float(audio_comp.get("smoothing") or 0.65)
    if "bassEmphasis" in audio_comp:
        audio["bassEmphasis"] = float(audio_comp.get("bassEmphasis") or 1.0)
    out["audioSettings"] = audio

    layers = out.get("layers") if isinstance(out.get("layers"), list) else []
    if layers and (
        "glow" in spec
        or "opacity" in spec
        or "blur" in spec
        or "barWidthScale" in spec
        or "thicknessScale" in spec
    ):
        try:
            raw_glow = spec.get("glow")
            expert_glow = max(0.0, min(1.0, float(0.45 if raw_glow is None else raw_glow)))
        except (TypeError, ValueError):
            expert_glow = 0.45
        try:
            expert_opacity = max(0.1, min(1.0, float(spec.get("opacity") or 1.0)))
        except (TypeError, ValueError):
            expert_opacity = 1.0
        try:
            raw_blur = spec.get("blur")
            expert_blur = max(0.0, min(8.0, float(0.0 if raw_blur is None else raw_blur)))
        except (TypeError, ValueError):
            expert_blur = 0.0
        try:
            bw_scale = max(0.08, min(3.0, float(spec.get("barWidthScale") or 1.0)))
        except (TypeError, ValueError):
            bw_scale = 1.0
        try:
            th_scale = max(0.25, min(3.0, float(spec.get("thicknessScale") or 1.0)))
        except (TypeError, ValueError):
            th_scale = 1.0
        tuned = []
        for layer in layers:
            if not isinstance(layer, dict):
                tuned.append(layer)
                continue
            item = dict(layer)
            mat_glow = float(item.get("glow") or 0.0)
            item["materialGlow"] = mat_glow
            item["materialOpacity"] = float(item.get("opacity") or 1.0)
            # Per-layer glow wins; else expert Glow 0 disables bloom.
            if item.get("layerGlow") is not None:
                lg = float(item.get("layerGlow") or 0.0)
                item["glow"] = 0.0 if lg <= 1e-6 else lg * 100.0
                item["expertGlow"] = lg
            elif expert_glow <= 1e-6:
                item["glow"] = 0.0
                item["expertGlow"] = 0.0
            else:
                item["glow"] = mat_glow * (0.35 + 1.4 * expert_glow) + expert_glow * 3.0
                item["expertGlow"] = expert_glow
            item["opacity"] = float(item["materialOpacity"]) * expert_opacity
            if item.get("layerBlur") is not None:
                item["blur"] = float(item.get("layerBlur") or 0.0)
            else:
                item["blur"] = float(item.get("blur") or 0.0) + expert_blur
            # Per-layer width/thickness already stamped in expand_spectrum_layers.
            if item.get("barWidthScale") is None:
                item["barWidth"] = max(0.15, float(item.get("barWidth") or 4.0) * bw_scale)
            if item.get("thicknessScale") is None and item.get("barHeight") is None:
                item["thickness"] = max(4.0, float(item.get("thickness") or 36.0) * th_scale)
            tuned.append(item)
        out["layers"] = tuned

    # Spectrum bar geometry — prefer per-layer controls; spectrum-level = fallback only.
    src_layers = out.get("layers") if isinstance(out.get("layers"), list) else []
    if src_layers:
        try:
            authored_bars = int(round(max(24, min(160, float(spec.get("barCount") or 64)))))
        except (TypeError, ValueError):
            authored_bars = 64
        try:
            tip_taper = max(0.0, min(1.0, float(0.0 if spec.get("tipTaper") is None else spec.get("tipTaper"))))
        except (TypeError, ValueError):
            tip_taper = 0.0
        mirrored = spec.get("mirrored")
        peak_caps = bool(spec.get("peakCapsEnabled", False))
        solid_band = bool(spec.get("solidBand", False))
        gravity_override = spec.get("gravity")
        if gravity_override not in (None, "", "none", "auto"):
            try:
                from visualizer._spectrum_fast import normalize_spectrum_gravity

                gravity_override = normalize_spectrum_gravity(gravity_override)
            except Exception:
                gravity_override = None
        else:
            gravity_override = None

        def _apply_bar_geometry(source: list[Any]) -> list[Any]:
            tuned_g: list[Any] = []
            for layer in source:
                if not isinstance(layer, dict):
                    tuned_g.append(layer)
                    continue
                item = dict(layer)
                if item.get("barCount") is None:
                    item["barCount"] = authored_bars
                if item.get("tipTaper") is None:
                    item["tipTaper"] = tip_taper
                if item.get("mirrored") is None and mirrored is not None:
                    item["mirrored"] = bool(mirrored)
                if item.get("gravity") is None and gravity_override is not None:
                    item["gravity"] = gravity_override
                if "peakCapsEnabled" not in item:
                    item["peakCapsEnabled"] = peak_caps
                if "solidBand" not in item:
                    item["solidBand"] = solid_band
                tuned_g.append(item)
            return tuned_g

        out["layers"] = _apply_bar_geometry(src_layers)
        instances = out.get("spectrumInstances")
        if isinstance(instances, list) and instances:
            synced_g: list[Any] = []
            for inst in instances:
                if not isinstance(inst, dict):
                    synced_g.append(inst)
                    continue
                item = dict(inst)
                inst_layers = item.get("layers") if isinstance(item.get("layers"), list) else []
                if inst_layers:
                    item["layers"] = _apply_bar_geometry(inst_layers)
                synced_g.append(item)
            out["spectrumInstances"] = synced_g

    logo_comp = comp.get("logo") if isinstance(comp.get("logo"), dict) else {}
    ls = out.get("logoSettings") if isinstance(out.get("logoSettings"), dict) else {}
    ls = dict(ls)
    base_size = float(logo_comp.get("size") or ls.get("size") or 192.0)
    scale = float(logo_comp.get("scale") or 1.0)
    ls["scale"] = scale
    ls["size"] = base_size * scale
    ls["motionZoomStrength"] = scale
    if "opacity" in logo_comp:
        ls["opacity"] = float(logo_comp.get("opacity") or 1.0)
    if "reactivity" in logo_comp:
        ls["reactivity"] = float(logo_comp.get("reactivity") or 0.0)
    if "offsetX" in logo_comp:
        ls["offsetX"] = float(logo_comp.get("offsetX") or 0.0) * 480.0
    if "offsetY" in logo_comp:
        ls["offsetY"] = float(logo_comp.get("offsetY") or 0.0) * 270.0
    out["logoSettings"] = ls

    text_comp = comp.get("text") if isinstance(comp.get("text"), dict) else {}
    overlays = out.get("textOverlays") if isinstance(out.get("textOverlays"), list) else []
    if overlays and text_comp:
        t_opacity = float(text_comp.get("opacity") or 1.0)
        t_scale = float(text_comp.get("scale") or 1.0)
        t_off = float(text_comp.get("offsetY") or 0.0)
        tuned_t = []
        for ov in overlays:
            if not isinstance(ov, dict):
                tuned_t.append(ov)
                continue
            item = dict(ov)
            item["opacity"] = t_opacity
            item["scale"] = t_scale
            item["offsetY"] = t_off
            tuned_t.append(item)
        out["textOverlays"] = tuned_t

    part_comp = comp.get("particles") if isinstance(comp.get("particles"), dict) else {}
    ps = out.get("particlesSettings") if isinstance(out.get("particlesSettings"), dict) else {}
    ps = dict(ps)
    if "spawn" in part_comp:
        ps["spawnRate"] = float(ps.get("spawnRate") or 100.0) * float(part_comp.get("spawn") or 1.0)
    if "size" in part_comp:
        ps["size"] = float(ps.get("size") or 2.0) * float(part_comp.get("size") or 1.0)
    if "opacity" in part_comp:
        ps["opacity"] = float(part_comp.get("opacity") or 0.35)
    if "speed" in part_comp:
        ps["speed"] = float(ps.get("speed") or 1.0) * float(part_comp.get("speed") or 1.0)
    if "reactivity" in part_comp:
        ps["reactStrength"] = float(part_comp.get("reactivity") or 0.45)
        ps["reactivity"] = float(part_comp.get("reactivity") or 0.45)
    out["particlesSettings"] = ps

    light_comp = comp.get("lighting") if isinstance(comp.get("lighting"), dict) else {}
    lighting = out.get("lightingSettings") if isinstance(out.get("lightingSettings"), dict) else {}
    lighting = dict(lighting)
    if light_comp:
        draw = lighting.get("draw") if isinstance(lighting.get("draw"), dict) else {}
        draw = dict(draw)
        if "intensity" in light_comp:
            draw["intensity"] = float(light_comp.get("intensity") or 0.85)
        lighting["draw"] = draw
        if "thickness" in light_comp:
            lighting["thickness"] = float(light_comp.get("thickness") or 1.0) * float(
                (_LIGHTING_PROFILES.get(str(lighting.get("effectId") or "")) or {}).get("thickness") or 2.8
            )
        if "glow" in light_comp:
            lighting["glow"] = float(light_comp.get("glow") or 0.55)
        if "flashRate" in light_comp:
            lighting["flashRate"] = float(light_comp.get("flashRate") or 0.85)
        if "speed" in light_comp:
            lighting["speed"] = float(light_comp.get("speed") or 1.0)
        out["lightingSettings"] = lighting
        layers_l = out.get("lightningLayers") if isinstance(out.get("lightningLayers"), list) else []
        if layers_l:
            tuned_l = []
            for layer in layers_l:
                if not isinstance(layer, dict):
                    tuned_l.append(layer)
                    continue
                item = dict(layer)
                if "intensity" in light_comp:
                    item["intensity"] = float(light_comp.get("intensity") or 0.85)
                if "thickness" in light_comp:
                    item["thickness"] = float(item.get("thickness") or 2.8) * float(
                        light_comp.get("thickness") or 1.0
                    )
                if "glow" in light_comp:
                    item["glow"] = float(light_comp.get("glow") or 0.55)
                if "flashRate" in light_comp:
                    item["flashRate"] = float(light_comp.get("flashRate") or 0.85)
                if "speed" in light_comp:
                    item["speed"] = float(light_comp.get("speed") or 1.0)
                    item["reactMotionSpeed"] = float(light_comp.get("speed") or 1.0)
                tuned_l.append(item)
            out["lightningLayers"] = tuned_l

    cam_comp = comp.get("camera") if isinstance(comp.get("camera"), dict) else {}
    camera = out.get("cameraSettings") if isinstance(out.get("cameraSettings"), dict) else {}
    camera = dict(camera)
    if cam_comp:
        camera["zoomBias"] = float(cam_comp.get("zoomBias") or 1.0)
        camera["panX"] = float(cam_comp.get("panX") or 0.0)
        camera["panY"] = float(cam_comp.get("panY") or 0.0)
        camera["shakeAmount"] = float(cam_comp.get("shakeAmount") or 0.5)
        camera["roll"] = float(camera.get("roll") or 0.0) + float(cam_comp.get("rollBias") or 0.0)
        if float(camera["shakeAmount"]) > 0 and bool(camera.get("enabled")):
            shake = float(camera.get("shake") or 0.0)
            camera["shake"] = shake + 0.04 * float(camera["shakeAmount"])
        out["cameraSettings"] = camera

    post_comp = comp.get("postProcessing") if isinstance(comp.get("postProcessing"), dict) else {}
    post_amount = float(post_comp.get("amount") or 0.35) if post_comp else 0.35
    effects = out.get("effects") if isinstance(out.get("effects"), dict) else {}
    effects = dict(effects)
    for key, payload in list(effects.items()):
        if not isinstance(payload, dict) or not bool(payload.get("enabled")):
            continue
        if "amount" not in payload:
            continue
        # Scale authored post amounts toward expert stack amount (keep relative feel).
        base = float(payload.get("amount") or 0.3)
        effects[key] = {**payload, "amount": max(0.02, min(1.0, base * (0.5 + post_amount)))}
    out["effects"] = effects

    perf = comp.get("performance") if isinstance(comp.get("performance"), dict) else {}
    if perf:
        quality = str(perf.get("quality") or "medium").strip().lower()
        if quality not in ("low", "medium", "high"):
            quality = "medium"
        lod = bool(perf.get("lod", True))
        out["performanceSettings"] = {"quality": quality, "lod": lod}
        # Scale authored barCount by quality/LOD (keeps Shape "Bar count" meaningful).
        quality_scale = {"low": 0.55, "medium": 1.0, "high": 1.75}[quality]
        if not lod:
            quality_scale *= 1.25

        def _scale_bar_count(raw: Any) -> int:
            try:
                base = int(round(float(raw if raw is not None else 64)))
            except (TypeError, ValueError):
                base = 64
            return int(max(24, min(160, round(base * quality_scale))))

        layers = out.get("layers") if isinstance(out.get("layers"), list) else []
        tuned_layers: list[Any] = []
        for layer in layers:
            if not isinstance(layer, dict):
                tuned_layers.append(layer)
                continue
            item = dict(layer)
            item["barCount"] = _scale_bar_count(item.get("barCount"))
            tuned_layers.append(item)
        if tuned_layers:
            out["layers"] = tuned_layers
        instances = out.get("spectrumInstances")
        if isinstance(instances, list) and instances:
            synced_inst: list[Any] = []
            for inst in instances:
                if not isinstance(inst, dict):
                    synced_inst.append(inst)
                    continue
                item = dict(inst)
                inst_layers = item.get("layers") if isinstance(item.get("layers"), list) else []
                item["layers"] = [
                    {**layer, "barCount": _scale_bar_count(layer.get("barCount"))}
                    if isinstance(layer, dict)
                    else layer
                    for layer in inst_layers
                ]
                synced_inst.append(item)
            out["spectrumInstances"] = synced_inst
        # Particles: lower quality thins spawn; LOD-off allows denser emitters.
        ps = out.get("particlesSettings") if isinstance(out.get("particlesSettings"), dict) else {}
        if ps:
            ps = dict(ps)
            spawn = float(ps.get("spawnRate") or 100.0)
            scale = {"low": 0.55, "medium": 1.0, "high": 1.45}[quality]
            if not lod:
                scale *= 1.25
            ps["spawnRate"] = max(8.0, spawn * scale)
            out["particlesSettings"] = ps
