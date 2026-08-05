"""Composition Engine V1 — compile Scene → draw state (engine authority)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from visualizer.animations import evaluate_behavior, spectrum_audio_from_behavior
from visualizer.composition_effects.particles import build_particle_emitter
from visualizer.materials import apply_material_to_layers
from visualizer.presets.palettes import get_palette
from visualizer.presets.shapes import build_shape_layers, normalize_spectrum_shape_id
from visualizer.scene import NONE, Scene, load_scene


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
    palette_id: str | None = None
    pass_meta: dict[str, Any] = field(default_factory=dict)

    def to_renderer_dict(self) -> dict[str, Any]:
        """Map compiled state into the GPU draw dict (internal only).

        User/docs must not treat these keys as the scene contract — they are
        compiler output consumed by preview/export.
        """
        assets = self.assets
        particles = deepcopy(self.particles) if self.particles else {"enabled": False}
        # Map engine emitter → particle system fields the existing GPU understands,
        # without treating those fields as authoring authority.
        style = str(particles.get("style") or "dot")
        # Keep classic path for spark/dot/glow/ring/bokeh styles.
        variant = {
            "bokeh": "bokeh",
            "ring": "soap",
            "glow": "dust",
            "spark": "classic",
            "dot": "classic",
        }.get(style, "classic")

        logo_motion = self.logo.get("motion") or {}
        return {
            "schema": "camxora.composition",
            "composition": deepcopy(self.composition),
            "assets": deepcopy(assets),
            "spectrumEnabled": self.spectrum_shape != NONE,
            "layers": deepcopy(self.spectrum_layers),
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
                "style": style,
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
                "motionMode": "none" if self.background.get("motion") == "static" else "zoom",
                "path": assets.get("backgroundImage"),
            },
            "overlaySettings": {
                "enabled": bool(self.overlay.get("enabled", False)),
                "animation": self.overlay.get("animation", NONE),
                "items": list(self.overlay.get("items") or []),
            },
            "effects": {},
            "engine": {
                "compiled": True,
                "spectrum": {
                    "shape": self.spectrum_shape,
                    "material": self.spectrum_material,
                    "animation": self.spectrum_animation,
                    "motion": deepcopy(self.spectrum_motion),
                },
                "palette": self.palette_id,
            },
            # Intentionally omit user-facing legacy `style` authority.
        }


def compile_scene(
    scene_or_doc: Scene | dict[str, Any],
    *,
    time_sec: float = 0.0,
    audio_level: float = 0.0,
) -> CompiledFrame:
    scene = scene_or_doc if isinstance(scene_or_doc, Scene) else load_scene(scene_or_doc)
    comp = scene.composition
    assets = scene.assets
    palette = get_palette(comp.get("colorPalette"))
    solid = palette["solid"] if palette else "#ff4fd8"
    accent = palette["accent"] if palette else "#22d3ee"
    stops = list(palette["stops"]) if palette else [solid, accent, "#ffffff"]

    shape_id = normalize_spectrum_shape_id(comp["spectrum"]["shape"]) or (
        NONE if comp["spectrum"]["shape"] in (None, "", NONE) else None
    )
    if comp["spectrum"]["shape"] not in (None, "", NONE) and shape_id is None:
        raise ValueError(f"unknown spectrum shape: {comp['spectrum']['shape']!r}")

    material_id = str(comp["spectrum"]["material"] or NONE)
    animation_id = str(comp["spectrum"]["animation"] or NONE)

    layers: list[dict[str, Any]] = []
    if shape_id and shape_id != NONE:
        layers = build_shape_layers(shape_id)
        if material_id and material_id != NONE:
            layers = apply_material_to_layers(layers, material_id)
        for layer in layers:
            layer["color"] = {
                "mode": "gradient",
                "solidColor": solid,
                "gradientColors": list(stops),
                "gradientDirection": "left-to-right",
            }
        motion = evaluate_behavior(animation_id, time_sec=time_sec, audio_level=audio_level, target="spectrum")
        for layer in layers:
            layer["opacity"] = float(layer.get("opacity", 1.0)) * float(motion["opacity"])
            layer["rotation"] = float(layer.get("rotation", 0.0) or 0.0) + float(motion["rotation"])
            layer["animationId"] = animation_id if animation_id != NONE else NONE
        spectrum_audio = spectrum_audio_from_behavior(animation_id if animation_id != NONE else None)
        spectrum_motion = {k: float(v) for k, v in motion.items() if k != "behavior_id"}
    else:
        spectrum_audio = {}
        spectrum_motion = {}
        shape_id = NONE

    particle_type = str(comp["particles"]["type"] or NONE)
    particle_behavior = str(comp["particles"]["behavior"] or NONE)
    particles = None
    if particle_type != NONE:
        particles = build_particle_emitter(
            particle_type,
            particle_behavior if particle_behavior != NONE else None,
            palette_solid=solid,
        )

    logo_anim = str(comp["logo"]["animation"] or NONE)
    logo_motion = evaluate_behavior(logo_anim, time_sec=time_sec, audio_level=audio_level, target="logo")
    overlay_anim = str(comp["overlay"].get("animation") or NONE)

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
        },
        overlay={
            "enabled": bool(comp["overlay"].get("enabled", False)),
            "animation": overlay_anim,
            "items": list(comp["overlay"].get("items") or []),
        },
        background={
            "motion": comp["background"].get("motion") or "static",
            "atmosphere": comp["background"].get("atmosphere") or NONE,
            "image": assets.get("backgroundImage") or comp["background"].get("image"),
        },
        palette_id=palette["id"] if palette else None,
        pass_meta={"time_sec": time_sec, "audio_level": audio_level},
    )
