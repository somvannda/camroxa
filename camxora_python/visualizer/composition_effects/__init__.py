"""Effects package — particles, lighting, camera, atmosphere, post, audio mapping."""

from __future__ import annotations

from visualizer.composition_effects.atmosphere import build_atmosphere_pass
from visualizer.composition_effects.gpu_bridge import apply_gpu_preview_bridge
from visualizer.composition_effects.audio_mapping import (
    apply_mapping_levels,
    normalize_audio_mapping,
    resolve_bus_levels,
)
from visualizer.composition_effects.background_motion import evaluate_background_motion
from visualizer.composition_effects.camera import evaluate_camera_behavior
from visualizer.composition_effects.lighting import build_lighting_pass
from visualizer.composition_effects.particles import build_particle_emitter, emitters_visibly_distinct
from visualizer.composition_effects.post import build_post_stack

__all__ = (
    "apply_gpu_preview_bridge",
    "apply_mapping_levels",
    "build_atmosphere_pass",
    "build_lighting_pass",
    "build_particle_emitter",
    "build_post_stack",
    "emitters_visibly_distinct",
    "evaluate_background_motion",
    "evaluate_camera_behavior",
    "normalize_audio_mapping",
    "resolve_bus_levels",
)
