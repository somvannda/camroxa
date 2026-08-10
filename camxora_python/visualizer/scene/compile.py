"""Composition Engine V1 — compile Scene → draw state (engine authority)."""



from __future__ import annotations



from copy import deepcopy

from dataclasses import dataclass, field

from typing import Any



from visualizer.animations import evaluate_behavior, spectrum_audio_from_behavior

from visualizer.composition_effects.atmosphere import build_atmosphere_pass

from visualizer.composition_effects.audio_mapping import (

    apply_mapping_levels,

    normalize_audio_mapping,

    resolve_bus_levels,

)

from visualizer.composition_effects.background_motion import evaluate_background_motion

from visualizer.composition_effects.camera import evaluate_camera_behavior

from visualizer.composition_effects.lighting import build_lighting_pass

from visualizer.composition_effects.particles import build_particle_emitter

from visualizer.composition_effects.post import build_post_stack

from visualizer.materials import apply_material_to_layers

from visualizer.presets.palettes import apply_palette_expert, clarify_palette, get_palette

from visualizer.presets.shapes import build_shape_layers, normalize_spectrum_shape_id

from visualizer.scene import NONE, Scene, load_scene

from visualizer.scene.spectrum_layers import expand_spectrum_layers, normalize_spectrum_layers





@dataclass

class CompiledFrame:

    """Internal draw payload generated from composition (not a user schema)."""



    composition: dict[str, Any]

    assets: dict[str, Any]

    spectrum_layers: list[dict[str, Any]] = field(default_factory=list)

    spectrum_shape: str = NONE

    spectrum_material: str = NONE

    spectrum_animation: str = NONE

    spectrum_motion: dict[str, float] = field(default_factory=dict)

    spectrum_audio: dict[str, float] = field(default_factory=dict)

    particles: dict[str, Any] | None = None

    logo: dict[str, Any] = field(default_factory=dict)

    overlay: dict[str, Any] = field(default_factory=dict)

    background: dict[str, Any] = field(default_factory=dict)

    lighting: dict[str, Any] | None = None

    camera: dict[str, Any] = field(default_factory=dict)

    atmosphere: dict[str, Any] | None = None

    post: dict[str, Any] = field(default_factory=dict)

    audio_mapping: dict[str, Any] = field(default_factory=dict)

    palette_id: str | None = None

    pass_meta: dict[str, Any] = field(default_factory=dict)



    def to_renderer_dict(self) -> dict[str, Any]:

        """Map compiled state into the GPU draw dict (internal only).



        User/docs must not treat these keys as the scene contract — they are

        compiler output consumed by preview/export.

        """

        assets = self.assets

        particles = deepcopy(self.particles) if self.particles else {"enabled": False}

        particle_style = str(particles.get("style") or "dot")

        variant = {

            "bokeh": "bokeh",

            "ring": "soap",

            "glow": "dust",

            "spark": "classic",

            "dot": "classic",

        }.get(particle_style, "classic")

        try:
            from features.video.lib.composition_spectrum_shapes import legacy_style_alias_for_shape

            spectrum_style = (
                legacy_style_alias_for_shape(self.spectrum_shape)
                if self.spectrum_shape not in (None, "", NONE)
                else "orbit-spikes"
            )
        except Exception:
            spectrum_style = "orbit-spikes"



        logo_motion = self.logo.get("motion") or {}

        bg_motion = self.background.get("evaluated") or {}

        post = self.post or {}

        camera = self.camera or {}



        return {

            "schema": "camxora.composition",

            "composition": deepcopy(self.composition),

            "assets": deepcopy(assets),

            "spectrumEnabled": self.spectrum_shape != NONE,

            "style": spectrum_style,

            "layers": deepcopy(self.spectrum_layers),

            "position": {

                "anchor": "center",

                "x": float(self.composition.get("spectrum", {}).get("offsetX") or 0.0) * 480.0,

                "y": float(self.composition.get("spectrum", {}).get("offsetY") or 0.0) * 270.0,

            },

            "audioSettings": {

                "sensitivity": 1.0,

                "smoothing": float(self.spectrum_audio.get("motionSmoothing", 0.65)),

                "inputGain": 1.0,

                "barHeight": float(self.spectrum_audio.get("barHeight", 1.0)),

                "kickImpact": float(self.spectrum_audio.get("kickImpact", 0.0)),

                "bassEmphasis": float(self.spectrum_audio.get("bassEmphasis", 1.0)),

                "motionSmoothing": float(self.spectrum_audio.get("motionSmoothing", 0.65)),

            },

            "logoPath": assets.get("logo") or "",

            "previewLogo": assets.get("logo") or "",

            "previewBackground": assets.get("backgroundImage") or "",

            "logoSettings": {

                "enabled": bool(self.logo.get("enabled", True)),

                "spinEnabled": float(logo_motion.get("rotation", 0.0)) != 0.0

                or self.logo.get("animation") == "rotate",

                "spinSpeed": float(logo_motion.get("rotation", 0.0)) * 2.0,

                "motionMode": "zoom" if float(logo_motion.get("scale", 1.0)) != 1.0 else "none",

                "motionZoomStrength": float(logo_motion.get("scale", 1.0)),

                "opacity": float(logo_motion.get("opacity", 1.0)),

                "animationId": self.logo.get("animation", NONE),

            },

            "particlesSettings": {

                "enabled": bool(particles.get("enabled", False)),

                "maxCount": int(particles.get("maxCount", 200) or 200),

                "spawnRate": float(particles.get("spawnRate", 100) or 100),

                "lifetimeSec": float(particles.get("lifetimeSec", 1.6) or 1.6),

                "speed": float(particles.get("speed", 1.0) or 1.0),

                "size": float(particles.get("size", 2.0) or 2.0),

                "opacity": float(particles.get("opacity", 0.35) or 0.35),

                "color": particles.get("color") or "#ffffff",

                "reactColor": particles.get("reactColor") or "#ffffff",

                "style": particle_style,

                "variant": variant,

                "spawnArea": particles.get("spawnArea") or "centerRing",

                "travelMode": particles.get("travelMode") or "spawnFlow",

                "sizeJitter": float(particles.get("sizeJitter", 0.0) or 0.0),

                "drift": float(particles.get("drift", 0.0) or 0.0),

                "swirl": float(particles.get("swirl", 0.0) or 0.0),

                "reactStrength": float(particles.get("reactStrength", 0.45) or 0.45),

                "spawnMode": "always",

                "spawnTrigger": "both",

                "typeId": particles.get("typeId") or NONE,

                "behaviorId": particles.get("behaviorId") or NONE,

            },

            "backgroundSettings": {

                "motionMode": bg_motion.get("legacyMotionMode") or (

                    "none" if self.background.get("motion") == "static" else "zoom"

                ),

                "path": assets.get("backgroundImage"),

                "motionId": self.background.get("motion"),

                "atmosphereId": self.background.get("atmosphere"),

                "evaluated": deepcopy(bg_motion),

            },

            "overlaySettings": {

                "enabled": bool(self.overlay.get("enabled", False)),

                "animation": self.overlay.get("animation", NONE),

                "items": list(self.overlay.get("items") or []),

            },

            "effects": deepcopy(post.get("gpuEffects") or {}),

            "lightingSettings": deepcopy(self.lighting) if self.lighting else {"enabled": False},

            "cameraSettings": deepcopy(camera),

            "atmosphereSettings": deepcopy(self.atmosphere) if self.atmosphere else {"enabled": False},

            "postProcessingSettings": {

                "enabled": bool(post.get("enabled")),

                "effects": deepcopy(post.get("effects") or []),

            },

            "audioMapping": deepcopy(self.audio_mapping),

            "engine": {

                "compiled": True,

                "spectrum": {

                    "shape": self.spectrum_shape,

                    "material": self.spectrum_material,

                    "animation": self.spectrum_animation,

                    "motion": deepcopy(self.spectrum_motion),

                },

                "palette": self.palette_id,

                "lighting": (self.lighting or {}).get("effectId"),

                "camera": camera.get("behaviorId"),

                "atmosphere": (self.atmosphere or {}).get("atmosphereId"),

                "postCount": len(post.get("effects") or []),

            },

        }





def compile_scene(

    scene_or_doc: Scene | dict[str, Any],

    *,

    time_sec: float = 0.0,

    audio_level: float = 0.0,

    audio_buses: dict[str, float] | None = None,

) -> CompiledFrame:

    scene = scene_or_doc if isinstance(scene_or_doc, Scene) else load_scene(scene_or_doc)

    comp = scene.composition

    assets = scene.assets

    palette = get_palette(comp.get("colorPalette"))
    try:
        # Use None-check — ``0.0 or 1.0`` wrongly forced intensity back to 1.0.
        raw_i = comp.get("paletteIntensity")
        pal_intensity = float(1.0 if raw_i is None else raw_i)
    except (TypeError, ValueError):
        pal_intensity = 1.0
    try:
        raw_s = comp.get("paletteSaturation")
        pal_saturation = float(1.0 if raw_s is None else raw_s)
    except (TypeError, ValueError):
        pal_saturation = 1.0
    palette = apply_palette_expert(palette, intensity=pal_intensity, saturation=pal_saturation)

    solid = palette["solid"] if palette else "#ff4fd8"

    accent = palette["accent"] if palette else "#22d3ee"

    stops = list(palette["stops"]) if palette else [solid, accent, "#ffffff"]

    # Spectrum may override the global palette; None/empty inherits global.
    # Clarify pushes pastel catalog stops toward neon “true color” bars.
    spec_palette = get_palette((comp.get("spectrum") or {}).get("colorPalette"))
    if spec_palette is not None:
        spec_palette = apply_palette_expert(
            spec_palette,
            intensity=pal_intensity,
            saturation=max(pal_saturation, 1.15),
        )
    spectrum_palette = clarify_palette(
        spec_palette if spec_palette is not None else palette,
        amount=0.4,
    )
    spectrum_solid = spectrum_palette["solid"] if spectrum_palette else solid
    spectrum_accent = spectrum_palette["accent"] if spectrum_palette else accent
    spectrum_stops = (
        list(spectrum_palette["stops"]) if spectrum_palette else list(stops)
    )
    custom_stops = (comp.get("spectrum") or {}).get("gradientColors")
    if isinstance(custom_stops, list) and len(custom_stops) >= 2:
        from features.video.lib.spectrum_color_engine import normalize_spectrum_gradient_colors

        spectrum_stops = normalize_spectrum_gradient_colors(
            [str(c) for c in custom_stops],
            spectrum_solid,
        )
        spectrum_solid = str(spectrum_stops[0])
        spectrum_accent = str(spectrum_stops[min(1, len(spectrum_stops) - 1)])
    if not spectrum_stops:
        spectrum_stops = [spectrum_solid, spectrum_accent, "#ffffff"]



    shape_id = normalize_spectrum_shape_id(comp["spectrum"]["shape"]) or (

        NONE if comp["spectrum"]["shape"] in (None, "", NONE) else None

    )

    if comp["spectrum"]["shape"] not in (None, "", NONE) and shape_id is None:

        raise ValueError(f"unknown spectrum shape: {comp['spectrum']['shape']!r}")



    material_id = str(comp["spectrum"]["material"] or NONE)

    animation_id = str(comp["spectrum"]["animation"] or NONE)



    layers: list[dict[str, Any]] = []

    if shape_id and shape_id != NONE:

        template_layers = build_shape_layers(shape_id)

        if material_id and material_id != NONE:

            template_layers = apply_material_to_layers(template_layers, material_id)

        size_scale = float(comp["spectrum"].get("sizeScale") or 1.0)

        authored = normalize_spectrum_layers(
            comp["spectrum"].get("layers"), defaults=comp["spectrum"]
        )

        layers = expand_spectrum_layers(
            template_layers, authored, size_scale=size_scale, defaults=comp["spectrum"]
        )

        for layer in layers:

            layer["color"] = {

                "mode": "gradient",

                "solidColor": spectrum_solid,

                "gradientColors": list(spectrum_stops),

                "gradientDirection": "left-to-right",

            }

        try:
            anim_speed = max(
                0.15,
                min(
                    3.0,
                    float(
                        1.0
                        if comp["spectrum"].get("animationSpeed") is None
                        else comp["spectrum"].get("animationSpeed")
                    ),
                ),
            )
        except (TypeError, ValueError):
            anim_speed = 1.0
        motion = evaluate_behavior(
            animation_id,
            time_sec=time_sec,
            audio_level=audio_level,
            target="spectrum",
            speed=anim_speed,
            scale_amount=float(comp["spectrum"].get("animationScaleAmount") or 1.0),
            opacity_amount=float(comp["spectrum"].get("animationOpacityAmount") or 1.0),
            rotate_amount=float(comp["spectrum"].get("animationRotateAmount") or 1.0),
            audio_amount=float(comp["spectrum"].get("animationAudioAmount") or 1.0),
        )

        grav_override = comp["spectrum"].get("gravity")
        if grav_override not in (None, "", "none", "auto"):
            try:
                from visualizer._spectrum_fast import normalize_spectrum_gravity

                grav_override = normalize_spectrum_gravity(grav_override)
            except Exception:
                grav_override = None
        else:
            grav_override = None

        for layer in layers:

            layer["opacity"] = float(layer.get("opacity", 1.0)) * float(motion["opacity"])

            layer["rotation"] = float(layer.get("rotation", 0.0) or 0.0) + float(motion["rotation"])

            layer["animScale"] = float(motion.get("scale") or 1.0)

            layer["animationId"] = animation_id if animation_id != NONE else NONE

            if grav_override is not None and layer.get("gravity") is None:
                layer["gravity"] = grav_override

        spectrum_audio = spectrum_audio_from_behavior(animation_id if animation_id != NONE else None)
        try:
            kick_mul = max(0.0, min(2.5, float(comp["spectrum"].get("animationKick") or 1.0)))
        except (TypeError, ValueError):
            kick_mul = 1.0
        try:
            smooth_override = comp["spectrum"].get("animationSmoothing")
            if smooth_override is not None:
                spectrum_audio["motionSmoothing"] = max(0.1, min(1.0, float(smooth_override)))
        except (TypeError, ValueError):
            pass
        spectrum_audio["kickImpact"] = float(spectrum_audio.get("kickImpact") or 0.0) * kick_mul

        spectrum_motion = {k: float(v) for k, v in motion.items() if k != "behavior_id"}

    else:

        spectrum_audio = {}

        spectrum_motion = {}

        shape_id = NONE



    particle_type = str(comp["particles"]["type"] or NONE)

    particle_behavior = str(comp["particles"]["behavior"] or NONE)

    particles = None

    if particle_type != NONE:

        # Keep type-native colors unless an authored palette is selected.
        particles = build_particle_emitter(

            particle_type,

            particle_behavior if particle_behavior != NONE else None,

            palette_solid=solid if palette else None,

        )



    logo_anim = str(comp["logo"]["animation"] or NONE)

    logo_motion = evaluate_behavior(logo_anim, time_sec=time_sec, audio_level=audio_level, target="logo")

    overlay_anim = str(comp["overlay"].get("animation") or NONE)



    mapping = normalize_audio_mapping(comp.get("audio", {}).get("mapping"))

    # Prefer explicit bus levels; otherwise derive proxies from overall audio_level.

    if audio_buses:

        bus_levels = resolve_bus_levels(

            bass=float(audio_buses.get("bass", audio_level)),

            treble=float(audio_buses.get("treble", audio_level * 0.6)),

            kick=float(audio_buses.get("kick", audio_level)),

            overall=float(audio_buses.get("overall_loudness", audio_level)),

            mid=float(audio_buses.get("melody", audio_level * 0.7)),

            presence=float(audio_buses.get("vocals", audio_level * 0.65)),

            transient_mid=float(audio_buses.get("snare", audio_level * 0.5)),

        )

    else:

        bus_levels = resolve_bus_levels(

            bass=audio_level,

            treble=audio_level * 0.6,

            kick=audio_level,

            overall=audio_level,

            mid=audio_level * 0.7,

            presence=audio_level * 0.65,

            transient_mid=audio_level * 0.5,

        )

    mapped_levels = apply_mapping_levels(mapping, bus_levels)



    # Lighting trigger: prefer composition.lighting.trigger, else audio mapping.

    lighting_trigger = str(comp["lighting"].get("trigger") or NONE)

    if lighting_trigger == NONE and mapping.get("lighting") not in (None, NONE):

        lighting_trigger = mapping["lighting"]

    lighting_drive = float(bus_levels.get(lighting_trigger, 0.0)) if lighting_trigger != NONE else audio_level

    lighting = build_lighting_pass(

        comp["lighting"].get("effect"),

        lighting_trigger,

        palette_solid=solid,

    )

    if lighting:

        lighting["drive"] = lighting_drive

        lighting["mappedDrive"] = float(mapped_levels.get("lighting", 0.0))



    camera = evaluate_camera_behavior(

        comp["camera"].get("behavior"),

        time_sec=time_sec,

        audio_level=max(audio_level, float(mapped_levels.get("camera", 0.0))),

    )

    if mapped_levels.get("camera", 0.0) > 0 and camera.get("behaviorId") == "shake":

        camera["shake"] = float(camera.get("shake", 0.0)) + 0.04 * float(mapped_levels["camera"])



    bg_motion_id = str(comp["background"].get("motion") or "static")

    bg_eval = evaluate_background_motion(
        bg_motion_id,
        time_sec=time_sec,
        speed=float(comp["background"].get("motionSpeed") or 1.0),
        amplitude=float(comp["background"].get("motionAmplitude") or 1.0),
        zoom_amount=float(comp["background"].get("motionZoom") or 1.0),
        warp_amount=float(comp["background"].get("motionWarp") or 1.0),
    )

    atmosphere = build_atmosphere_pass(
        comp["background"].get("atmosphere"),
        density_scale=float(comp["background"].get("atmosphereDensity") or 1.0),
        speed_scale=float(comp["background"].get("atmosphereSpeed") or 1.0),
        opacity_scale=float(comp["background"].get("atmosphereOpacity") or 1.0),
        wind_scale=float(comp["background"].get("atmosphereWind") or 1.0),
    )

    post = build_post_stack(comp.get("postProcessing", {}).get("effects"))



    # Particles emit drive from mapping when present.

    if particles and mapped_levels.get("particles", 0.0) > 0:

        particles = dict(particles)

        particles["mappedEmit"] = float(mapped_levels["particles"])

        particles["reactStrength"] = min(

            1.0,

            float(particles.get("reactStrength", 0.45)) + 0.3 * float(mapped_levels["particles"]),

        )



    # Logo pulse from vocals/mapping.

    logo_drive = float(mapped_levels.get("logo", 0.0))

    if logo_drive > 0:

        logo_motion = dict(logo_motion)

        logo_motion["scale"] = float(logo_motion.get("scale", 1.0)) * (1.0 + 0.08 * logo_drive)



    return CompiledFrame(

        composition=deepcopy(comp),

        assets=deepcopy(assets),

        spectrum_layers=layers,

        spectrum_shape=shape_id or NONE,

        spectrum_material=material_id,

        spectrum_animation=animation_id,

        spectrum_motion=spectrum_motion,

        spectrum_audio=spectrum_audio,

        particles=particles,

        logo={

            "enabled": bool(comp["logo"].get("enabled", True)),

            "animation": logo_anim,

            "motion": {k: float(v) for k, v in logo_motion.items() if k != "behavior_id"},

            "path": assets.get("logo"),

            "mappedPulse": logo_drive,

        },

        overlay={

            "enabled": bool(comp["overlay"].get("enabled", False)),

            "animation": overlay_anim,

            "items": list(comp["overlay"].get("items") or []),

        },

        background={

            "motion": bg_motion_id,

            "atmosphere": comp["background"].get("atmosphere") or NONE,

            "image": assets.get("backgroundImage") or comp["background"].get("image"),

            "evaluated": bg_eval,

        },

        lighting=lighting,

        camera=camera,

        atmosphere=atmosphere,

        post=post,

        audio_mapping={

            "mapping": mapping,

            "busLevels": bus_levels,

            "mappedLevels": mapped_levels,

            "heuristicBuses": ["vocals", "melody", "snare"],

        },

        palette_id=palette["id"] if palette else None,

        pass_meta={"time_sec": time_sec, "audio_level": audio_level},

    )


