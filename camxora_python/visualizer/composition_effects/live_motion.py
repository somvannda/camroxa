"""Per-frame composition drivers — keep Studio axes alive in GPU preview.

``document_to_renderer_dict`` freezes camera/bg/mapping at one ``time_sec``.
This module re-evaluates those axes onto an existing renderer template each paint
so orbit/pan/zoom/atmosphere motion/audio mapping are not fake static labels.
"""

from __future__ import annotations

from typing import Any

from visualizer.animations import evaluate_behavior, spectrum_audio_from_behavior
from visualizer.composition_effects.audio_mapping import (
    apply_mapping_levels,
    normalize_audio_mapping,
    resolve_bus_levels,
)
from visualizer.composition_effects.background_motion import evaluate_background_motion
from visualizer.composition_effects.camera import evaluate_camera_behavior
from visualizer.composition_effects.gpu_bridge import _GPU_MOTION
from visualizer.presets.palettes import apply_palette_expert, clarify_palette, get_palette
from visualizer.scene import NONE


def _expert_float(raw: Any, default: float, *, lo: float, hi: float) -> float:
    if raw is None:
        return float(default)
    try:
        return max(lo, min(hi, float(raw)))
    except (TypeError, ValueError):
        return float(default)


def _palette_color_bag(palette: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(palette, dict):
        return None
    solid = str(palette.get("solid") or "#ff4fd8")
    stops = list(palette.get("stops") or [solid])
    if not stops:
        stops = [solid]
    return {
        "mode": "gradient",
        "solidColor": solid,
        "gradientColors": stops,
        "gradientDirection": "left-to-right",
    }


def _apply_live_palette_colors(template: dict[str, Any], comp: dict[str, Any]) -> None:
    """Force palette onto spectrum / particles / lightning every frame.

    Spectrum uses ``composition.spectrum.colorPalette`` when set; otherwise inherits
    the global ``composition.colorPalette``. Particles/lighting always use global.
    Custom ``spectrum.gradientColors`` overrides catalog palettes.
    """
    intensity = _expert_float(comp.get("paletteIntensity"), 1.0, lo=0.0, hi=2.0)
    saturation = _expert_float(comp.get("paletteSaturation"), 1.0, lo=0.0, hi=2.0)
    global_palette = apply_palette_expert(
        get_palette(comp.get("colorPalette")),
        intensity=intensity,
        saturation=saturation,
    )
    spec_comp = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
    spectrum_override = get_palette(spec_comp.get("colorPalette"))
    spectrum_palette = clarify_palette(
        apply_palette_expert(
            spectrum_override if spectrum_override is not None else global_palette,
            intensity=intensity,
            saturation=max(saturation, 1.15),
        ),
        amount=0.4,
    )
    spectrum_color = _palette_color_bag(spectrum_palette)
    custom_stops = spec_comp.get("gradientColors")
    if isinstance(custom_stops, list) and len(custom_stops) >= 2:
        from features.video.lib.spectrum_color_engine import normalize_spectrum_gradient_colors

        stops = normalize_spectrum_gradient_colors(
            [str(c) for c in custom_stops],
            str((spectrum_color or {}).get("solidColor") or "#ff4fd8"),
        )
        spectrum_color = {
            "mode": "gradient",
            "solidColor": stops[0],
            "gradientColors": stops,
            "gradientDirection": "left-to-right",
        }
    global_color = _palette_color_bag(global_palette)

    def _tint_layers(layers: list[Any], color: dict[str, Any] | None) -> list[Any]:
        if color is None:
            return list(layers)
        out: list[Any] = []
        for layer in layers:
            if not isinstance(layer, dict):
                out.append(layer)
                continue
            item = dict(layer)
            item["color"] = dict(color)
            out.append(item)
        return out

    if spectrum_color is not None:
        layers = template.get("layers")
        if isinstance(layers, list) and layers:
            template["layers"] = _tint_layers(layers, spectrum_color)
        instances = template.get("spectrumInstances")
        if isinstance(instances, list) and instances:
            synced: list[Any] = []
            for inst in instances:
                if not isinstance(inst, dict):
                    synced.append(inst)
                    continue
                item = dict(inst)
                src = item.get("layers") if isinstance(item.get("layers"), list) else []
                if src:
                    item["layers"] = _tint_layers(src, spectrum_color)
                synced.append(item)
            template["spectrumInstances"] = synced

    if global_color is not None:
        solid = str(global_color.get("solidColor") or "#ff4fd8")
        ps = template.get("particlesSettings") if isinstance(template.get("particlesSettings"), dict) else {}
        if ps and bool(ps.get("enabled", True)):
            ps = dict(ps)
            ps["color"] = solid
            template["particlesSettings"] = ps

        lighting = template.get("lightingSettings") if isinstance(template.get("lightingSettings"), dict) else {}
        if lighting:
            lighting = dict(lighting)
            lighting["color"] = solid
            template["lightingSettings"] = lighting
        bolts = template.get("lightningLayers") if isinstance(template.get("lightningLayers"), list) else []
        if bolts:
            tinted_bolts: list[Any] = []
            for bolt in bolts:
                if not isinstance(bolt, dict):
                    tinted_bolts.append(bolt)
                    continue
                item = dict(bolt)
                prev = item.get("color") if isinstance(item.get("color"), dict) else {}
                item["color"] = {
                    "mode": str(prev.get("mode") or "gradient"),
                    "solidColor": solid,
                    "gradientColors": [solid, "#ffffff", solid],
                    "gradientDirection": str(prev.get("gradientDirection") or "left-to-right"),
                }
                tinted_bolts.append(item)
            template["lightningLayers"] = tinted_bolts

    if global_palette is not None or spectrum_override is not None:
        template["paletteSettings"] = {
            "intensity": intensity,
            "saturation": saturation,
            "paletteId": str(comp.get("colorPalette") or ""),
            "spectrumPaletteId": str(spec_comp.get("colorPalette") or "") or None,
        }


def apply_live_composition_motion(
    template: dict[str, Any],
    *,
    time_sec: float,
    bass: float = 0.0,
    treble: float = 0.0,
    kick: float = 0.0,
    beat: float = 0.0,
    onset: float = 0.0,
    mid: float | None = None,
) -> None:
    """Mutate ``template`` camera/bg/logo/particles/lighting/effects for ``time_sec``."""
    if not isinstance(template, dict):
        return
    if str(template.get("schema") or "") not in ("camxora.composition", "camxora.composition.v1"):
        # Still allow when composition payload is present (Studio drafts).
        if not isinstance(template.get("composition"), dict):
            return
    comp = template.get("composition") if isinstance(template.get("composition"), dict) else None
    if not isinstance(comp, dict):
        return

    t = float(time_sec or 0.0)
    overall = max(float(bass), float(treble), float(kick), float(beat))
    mid_v = float(mid) if mid is not None else (float(bass) + float(treble)) * 0.5
    presence = max(float(treble), mid_v * 0.85)
    transient = max(float(onset), float(kick) * 0.7)

    bus_levels = resolve_bus_levels(
        bass=float(bass),
        treble=float(treble),
        kick=float(kick),
        overall=overall,
        mid=mid_v,
        presence=presence,
        transient_mid=transient,
    )
    mapping_raw = None
    audio_block = comp.get("audio") if isinstance(comp.get("audio"), dict) else {}
    mapping_raw = audio_block.get("mapping")
    am = template.get("audioMapping") if isinstance(template.get("audioMapping"), dict) else {}
    if mapping_raw is None and isinstance(am.get("mapping"), dict):
        mapping_raw = am.get("mapping")
    mapping = normalize_audio_mapping(mapping_raw)
    mapped = apply_mapping_levels(mapping, bus_levels)
    template["audioMapping"] = {
        **am,
        "mapping": mapping,
        "busLevels": bus_levels,
        "mappedLevels": mapped,
        "heuristicBuses": ["vocals", "melody", "snare"],
    }

    audio_level = max(overall, float(mapped.get("camera") or 0.0), float(mapped.get("lighting") or 0.0))

    # --- Color palette (spectrum / particles / lighting) ---
    _apply_live_palette_colors(template, comp)

    # --- Camera ---
    cam_comp = comp.get("camera") if isinstance(comp.get("camera"), dict) else {}
    camera = evaluate_camera_behavior(
        cam_comp.get("behavior"),
        time_sec=t,
        audio_level=max(audio_level, float(mapped.get("camera") or 0.0)),
    )
    camera["zoomBias"] = float(cam_comp.get("zoomBias") or 1.0)
    camera["panX"] = float(cam_comp.get("panX") or 0.0)
    camera["panY"] = float(cam_comp.get("panY") or 0.0)
    camera["shakeAmount"] = float(cam_comp.get("shakeAmount") or 0.5)
    if float(camera["shakeAmount"]) > 0 and bool(camera.get("enabled")):
        camera["shake"] = float(camera.get("shake") or 0.0) + 0.04 * float(camera["shakeAmount"]) * float(
            mapped.get("camera") or audio_level or 0.35
        )
    template["cameraSettings"] = camera

    effects = template.get("effects") if isinstance(template.get("effects"), dict) else {}
    effects = dict(effects)
    shake_behaviors = {"shake", "handheld", "whip_pan", "punch_in"}
    behavior = str(camera.get("behaviorId") or NONE)
    if bool(camera.get("enabled")) and (
        behavior in shake_behaviors or float(camera.get("shake") or 0.0) > 0.0
    ):
        intensity = 8.0 + max(0.0, float(camera.get("shake") or 0.0)) * 120.0
        if behavior == "handheld":
            intensity = max(intensity, 6.0)
        intensity *= 0.65 + 0.7 * float(mapped.get("camera") or 0.4)
        effects["camera_shake"] = {
            "enabled": True,
            "intensity": float(min(24.0, intensity)),
            "smoothing": 0.85,
        }
    elif "camera_shake" in effects and behavior not in shake_behaviors:
        # Keep expert/manual shake off when behavior is calm orbit/pan.
        if behavior in ("orbit", "pan", "dolly", "crane", "drift", "parallax", "zoom", "tilt", "roll", "focus_pull", NONE, "none"):
            prev = effects.get("camera_shake")
            if isinstance(prev, dict) and float(camera.get("shakeAmount") or 0.0) <= 0.05:
                effects["camera_shake"] = {**prev, "enabled": False}

    # --- Background motion ---
    bg_comp = comp.get("background") if isinstance(comp.get("background"), dict) else {}
    motion_id = str(bg_comp.get("motion") or "static")
    ev = evaluate_background_motion(
        motion_id,
        time_sec=t,
        speed=_expert_float(bg_comp.get("motionSpeed"), 1.0, lo=0.15, hi=3.0),
        amplitude=_expert_float(bg_comp.get("motionAmplitude"), 1.0, lo=0.15, hi=3.0),
        zoom_amount=_expert_float(bg_comp.get("motionZoom"), 1.0, lo=0.15, hi=3.0),
        warp_amount=_expert_float(bg_comp.get("motionWarp"), 1.0, lo=0.0, hi=3.0),
    )
    bg = template.get("backgroundSettings") if isinstance(template.get("backgroundSettings"), dict) else {}
    bg = dict(bg)
    legacy = str(ev.get("legacyMotionMode") or "none")
    gpu_mode = _GPU_MOTION.get(legacy)
    if gpu_mode is None:
        gpu_mode = "none" if motion_id in ("", "static", NONE) else "zoom"
    bg["motionMode"] = gpu_mode
    bg["motionId"] = motion_id
    bg["evaluated"] = ev
    try:
        scale = float(ev.get("scale") or 1.0)
        zoom_boost = float(ev.get("zoomStrength") or 1.0)
        bg["motionZoomStrength"] = max(
            0.5, min(8.0, (abs(scale - 1.0) * 40.0 + 1.0) * max(0.5, zoom_boost))
        )
        bg["userScale"] = max(0.85, min(1.55, scale))
    except (TypeError, ValueError):
        bg["userScale"] = 1.0
    try:
        bg["motionVibrateStrength"] = max(0.2, min(8.0, float(ev.get("vibrateStrength") or 1.0)))
    except (TypeError, ValueError):
        bg["motionVibrateStrength"] = 1.0
    # Feed evaluator offsets into the plate transform the GPU already samples.
    # Rotate uses a wider orbit so it stays distinct from floating/parallax pans.
    offset_amp = 220.0 if motion_id == "rotate" else 180.0
    bg["userOffsetX"] = float(ev.get("offsetX") or 0.0) * offset_amp
    bg["userOffsetY"] = float(ev.get("offsetY") or 0.0) * offset_amp
    if "brightness" in bg_comp:
        bg["brightness"] = float(bg_comp.get("brightness") or 1.0)
    if "contrast" in bg_comp:
        bg["contrast"] = float(bg_comp.get("contrast") or 1.0)
    if "reactivity" in bg_comp:
        bg["reactivity"] = float(bg_comp.get("reactivity") or 0.0)
    template["backgroundSettings"] = bg

    # --- Atmosphere draw (rebuild live so Expert density/speed/wind apply) ---
    try:
        from visualizer.composition_effects.atmosphere import build_atmosphere_pass
        from visualizer.composition_effects.atmosphere_gpu import build_atmosphere_draw

        atm_pass = build_atmosphere_pass(
            bg_comp.get("atmosphere"),
            density_scale=_expert_float(bg_comp.get("atmosphereDensity"), 1.0, lo=0.0, hi=2.5),
            speed_scale=_expert_float(bg_comp.get("atmosphereSpeed"), 1.0, lo=0.1, hi=3.0),
            opacity_scale=_expert_float(bg_comp.get("atmosphereOpacity"), 1.0, lo=0.0, hi=1.0),
            wind_scale=_expert_float(bg_comp.get("atmosphereWind"), 1.0, lo=0.0, hi=3.0),
        )
        if atm_pass is None or not bool(atm_pass.get("enabled")):
            template.pop("atmosphereDraw", None)
            template["atmosphereSettings"] = {"enabled": False, "atmosphereId": NONE}
        else:
            template["atmosphereSettings"] = atm_pass
            draw = build_atmosphere_draw(atm_pass)
            if draw is not None:
                template["atmosphereDraw"] = draw
            else:
                template.pop("atmosphereDraw", None)
                template["atmosphereSettings"] = {"enabled": False, "atmosphereId": NONE}
    except Exception:
        pass

    # Warp / ripple get a soft-diffusion proxy so they don't collapse into plain zoom.
    warp = abs(float(ev.get("warp") or 0.0))
    if motion_id in ("ripple", "energy_wave", "warp") and warp > 1e-4:
        soft = effects.get("soft_diffusion") if isinstance(effects.get("soft_diffusion"), dict) else {}
        effects["soft_diffusion"] = {
            **(soft if isinstance(soft, dict) else {}),
            "enabled": True,
            "amount": max(0.08, min(0.55, 0.12 + warp * 4.0)),
        }
        if motion_id == "warp":
            lens = effects.get("lens_distortion") if isinstance(effects.get("lens_distortion"), dict) else {}
            effects["lens_distortion"] = {
                **(lens if isinstance(lens, dict) else {}),
                "enabled": True,
                "amount": max(0.08, min(0.4, warp * 3.0)),
            }

    # --- Spectrum animation (live opacity / rotation / scale / audio dials) ---
    # Preview paints ``spectrumInstances[*].layers`` (deep copies). Updating only
    # top-level ``layers`` left Animation looking dead while Shape still worked.
    spec_comp = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
    spec_anim = str(spec_comp.get("animation") or NONE)
    layers_live = template.get("layers") if isinstance(template.get("layers"), list) else []
    if layers_live and spec_anim not in ("", NONE, "none"):
        try:
            anim_speed = max(
                0.15,
                min(
                    3.0,
                    float(
                        1.0
                        if spec_comp.get("animationSpeed") is None
                        else spec_comp.get("animationSpeed")
                    ),
                ),
            )
        except (TypeError, ValueError):
            anim_speed = 1.0
        motion = evaluate_behavior(
            spec_anim,
            time_sec=t,
            audio_level=audio_level,
            target="spectrum",
            speed=anim_speed,
            scale_amount=float(spec_comp.get("animationScaleAmount") or 1.0),
            opacity_amount=float(spec_comp.get("animationOpacityAmount") or 1.0),
            rotate_amount=float(spec_comp.get("animationRotateAmount") or 1.0),
            audio_amount=float(spec_comp.get("animationAudioAmount") or 1.0),
        )
        hints = spectrum_audio_from_behavior(spec_anim)
        try:
            expert_bar = max(0.25, min(4.0, float(spec_comp.get("barHeight") or 1.0)))
        except (TypeError, ValueError):
            expert_bar = 1.0
        try:
            raw_glow = spec_comp.get("glow")
            expert_glow = max(0.0, min(1.0, float(0.45 if raw_glow is None else raw_glow)))
        except (TypeError, ValueError):
            expert_glow = 0.45
        try:
            expert_opacity = max(0.1, min(1.0, float(spec_comp.get("opacity") or 1.0)))
        except (TypeError, ValueError):
            expert_opacity = 1.0
        try:
            tip_taper = max(
                0.0,
                min(1.0, float(0.0 if spec_comp.get("tipTaper") is None else spec_comp.get("tipTaper"))),
            )
        except (TypeError, ValueError):
            tip_taper = 0.0
        try:
            kick_mul = max(0.0, min(2.5, float(spec_comp.get("animationKick") or 1.0)))
        except (TypeError, ValueError):
            kick_mul = 1.0
        audio = template.get("audioSettings") if isinstance(template.get("audioSettings"), dict) else {}
        audio = dict(audio)
        audio["barHeight"] = max(0.25, min(12.0, float(hints.get("barHeight") or 1.0) * expert_bar))
        audio["kickImpact"] = float(hints.get("kickImpact") or 0.0) * kick_mul
        audio["bassEmphasis"] = float(hints.get("bassEmphasis") or 1.0)
        try:
            smooth_override = spec_comp.get("animationSmoothing")
            if smooth_override is not None:
                audio["motionSmoothing"] = max(0.1, min(1.0, float(smooth_override)))
            else:
                audio["motionSmoothing"] = float(hints.get("motionSmoothing") or 0.65)
        except (TypeError, ValueError):
            audio["motionSmoothing"] = float(hints.get("motionSmoothing") or 0.65)
        audio["smoothing"] = float(audio["motionSmoothing"])
        # Kick/audio gain from animation boosts spectrum sensitivity live.
        audio["inputGain"] = max(
            float(audio.get("inputGain") or 1.0),
            0.75 + 0.9 * float(motion.get("audio_gain") or 0.0),
        )
        template["audioSettings"] = audio

        def _tune_spectrum_layers(source_layers: list[Any]) -> list[Any]:
            tuned: list[Any] = []
            for layer in source_layers:
                if not isinstance(layer, dict):
                    tuned.append(layer)
                    continue
                item = dict(layer)
                mat_glow = float(
                    item.get("materialGlow") if item.get("materialGlow") is not None else item.get("glow") or 0.0
                )
                mat_op = float(
                    item.get("materialOpacity")
                    if item.get("materialOpacity") is not None
                    else item.get("opacity")
                    or 1.0
                )
                item["materialGlow"] = mat_glow
                item["materialOpacity"] = mat_op
                if item.get("layerGlow") is not None:
                    lg = float(item.get("layerGlow") or 0.0)
                    item["glow"] = 0.0 if lg <= 1e-6 else lg * 100.0
                elif expert_glow <= 1e-6:
                    item["glow"] = 0.0
                else:
                    item["glow"] = mat_glow * (0.35 + 1.4 * expert_glow) + expert_glow * 3.0
                item["opacity"] = mat_op * float(motion.get("opacity") or 1.0) * expert_opacity
                item["rotation"] = float(motion.get("rotation") or 0.0)
                item["animScale"] = float(motion.get("scale") or 1.0)
                if item.get("tipTaper") is None:
                    item["tipTaper"] = tip_taper
                if item.get("layerBlur") is not None:
                    item["blur"] = float(item.get("layerBlur") or 0.0)
                item["animationId"] = spec_anim
                tuned.append(item)
            return tuned

        tuned_layers = _tune_spectrum_layers(layers_live)
        template["layers"] = tuned_layers

        instances = template.get("spectrumInstances")
        if isinstance(instances, list) and instances:
            synced: list[Any] = []
            for inst in instances:
                if not isinstance(inst, dict):
                    synced.append(inst)
                    continue
                item = dict(inst)
                src_layers = item.get("layers") if isinstance(item.get("layers"), list) else []
                item["layers"] = _tune_spectrum_layers(src_layers) if src_layers else list(tuned_layers)
                item["audioSettings"] = dict(audio)
                synced.append(item)
            template["spectrumInstances"] = synced

    # --- Logo animation ---
    logo_comp = comp.get("logo") if isinstance(comp.get("logo"), dict) else {}
    logo_anim = str(logo_comp.get("animation") or NONE)
    logo_motion = evaluate_behavior(
        logo_anim,
        time_sec=t,
        audio_level=max(audio_level, float(mapped.get("logo") or 0.0)),
        target="logo",
    )
    ls = template.get("logoSettings") if isinstance(template.get("logoSettings"), dict) else {}
    ls = dict(ls)
    rot = float(logo_motion.get("rotation") or 0.0)
    scale_m = float(logo_motion.get("scale") or 1.0)
    ls["spinEnabled"] = bool(rot != 0.0 or logo_anim == "rotate")
    ls["spinSpeed"] = rot * 2.0 if rot else float(ls.get("spinSpeed") or 0.0)
    if logo_anim == "rotate" and abs(ls["spinSpeed"]) < 1e-3:
        ls["spinEnabled"] = True
        ls["spinSpeed"] = 24.0
    base_scale = float(logo_comp.get("scale") or 1.0)
    ls["scale"] = base_scale * scale_m
    ls["size"] = float(ls.get("size") or 192.0)
    ls["opacity"] = float(logo_comp.get("opacity") or 1.0) * float(logo_motion.get("opacity") or 1.0)
    ls["reactivity"] = max(float(ls.get("reactivity") or 0.0), float(mapped.get("logo") or 0.0))
    ls["animationId"] = logo_anim
    if "circleMask" in logo_comp:
        ls["circleMask"] = bool(logo_comp.get("circleMask"))
    template["logoSettings"] = ls

    # --- Particles react to mapping ---
    ps = template.get("particlesSettings") if isinstance(template.get("particlesSettings"), dict) else {}
    if isinstance(ps, dict) and bool(ps.get("enabled")):
        ps = dict(ps)
        drive = float(mapped.get("particles") or 0.0)
        base_react = float(ps.get("reactStrength") or 0.45)
        ps["reactStrength"] = min(1.0, base_react + 0.35 * drive)
        ps["reactivity"] = max(float(ps.get("reactivity") or 0.0), drive)
        template["particlesSettings"] = ps

    # --- Lighting / lightning drive ---
    # Prefer composition Lighting Trigger bus; fall back to audio-mapping → lighting.
    layers = template.get("lightningLayers") if isinstance(template.get("lightningLayers"), list) else []
    if layers and bool(template.get("lightningEnabled")):
        light_comp = comp.get("lighting") if isinstance(comp.get("lighting"), dict) else {}
        trigger_id = str(light_comp.get("trigger") or NONE)
        if trigger_id not in ("", NONE, "none") and trigger_id in bus_levels:
            drive = float(bus_levels.get(trigger_id) or 0.0)
        else:
            drive = float(mapped.get("lighting") or 0.0)
        drive = max(drive, float(mapped.get("lighting") or 0.0) * 0.5)
        tuned = []
        for layer in layers:
            if not isinstance(layer, dict):
                tuned.append(layer)
                continue
            item = dict(layer)
            base_i = float(item.get("intensity") or 0.85)
            item["intensity"] = max(0.2, min(1.5, base_i * (0.55 + 0.7 * max(drive, audio_level * 0.5))))
            item["reactivity"] = max(float(item.get("reactivity") or 0.45), 0.35 + 0.55 * drive)
            tuned.append(item)
        template["lightningLayers"] = tuned

    # --- Overlay animation modulates effect amount ---
    overlay = comp.get("overlay") if isinstance(comp.get("overlay"), dict) else {}
    if bool(overlay.get("enabled")):
        oanim = str(overlay.get("animation") or NONE)
        amount = float(overlay.get("amount") or 0.28)
        if oanim not in ("", NONE, "none"):
            motion = evaluate_behavior(oanim, time_sec=t, audio_level=audio_level, target="overlay")
            amount *= float(motion.get("opacity") or 1.0) * (0.75 + 0.5 * float(motion.get("audio_gain") or 0.0))
        for key in ("film_grain", "rgb_split", "chromatic_aberration", "vignette", "bloom"):
            payload = effects.get(key)
            if isinstance(payload, dict) and bool(payload.get("enabled")):
                effects[key] = {**payload, "amount": max(0.02, min(1.0, amount))}

    # Map composition post keys onto uniforms the preview already samples.
    post = comp.get("postProcessing") if isinstance(comp.get("postProcessing"), dict) else {}
    post_amount = float(post.get("amount") or 0.35) if post else 0.35
    vig = effects.get("vignette") if isinstance(effects.get("vignette"), dict) else None
    if isinstance(vig, dict) and bool(vig.get("enabled")):
        amt = float(vig.get("amount") or post_amount)
        effects["vignette"] = {
            **vig,
            "strength": max(0.15, min(1.0, amt)),
            "opacity": max(0.25, min(1.0, 0.4 + amt * 0.7)),
        }
    bloom = effects.get("bloom") if isinstance(effects.get("bloom"), dict) else None
    if isinstance(bloom, dict) and bool(bloom.get("enabled")):
        amt = float(bloom.get("amount") or post_amount)
        effects["bloom"] = {
            **bloom,
            "strength": max(0.2, min(2.5, amt * 1.8)),
            "opacity": max(0.35, min(1.0, 0.5 + amt * 0.5)),
            "threshold": 0.55,
        }
    grain = effects.get("film_grain") if isinstance(effects.get("film_grain"), dict) else None
    if isinstance(grain, dict) and bool(grain.get("enabled")):
        amt = float(grain.get("amount") or 0.2)
        # Preview scene shader exposes smoke blur — reuse as grain/haze proxy.
        effects["smoke"] = {"enabled": True, "blur": max(0.15, min(1.0, amt)), "opacity": amt}

    template["effects"] = effects
