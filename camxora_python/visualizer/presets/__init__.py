"""Pure preset catalogs for Composition Engine V1 (no legacy painters)."""

from __future__ import annotations

from visualizer.presets.animations import (
    ANIMATION_BEHAVIOR_CATALOG,
    ANIMATION_BEHAVIOR_COUNT,
    ANIMATION_BEHAVIOR_IDS,
    list_animation_behavior_options,
    normalize_animation_behavior_id,
)
from visualizer.presets.materials import (
    SPECTRUM_MATERIAL_CATALOG,
    SPECTRUM_MATERIAL_COUNT,
    SPECTRUM_MATERIAL_IDS,
    get_material,
    list_spectrum_material_options,
    normalize_spectrum_material_id,
)
from visualizer.presets.palettes import (
    COLOR_PALETTE_CATALOG,
    COLOR_PALETTE_COUNT,
    COLOR_PALETTE_IDS,
    get_palette,
    list_color_palette_options,
    normalize_color_palette_id,
)
from visualizer.presets.particles import (
    PARTICLE_TYPE_CATALOG,
    PARTICLE_TYPE_COUNT,
    PARTICLE_TYPE_IDS,
    get_particle_type,
    list_particle_type_options,
    normalize_particle_type_id,
)
from visualizer.presets.shapes import (
    SPECTRUM_SHAPE_CATALOG,
    SPECTRUM_SHAPE_COUNT,
    SPECTRUM_SHAPE_IDS,
    build_shape_layers,
    list_spectrum_shape_options,
    normalize_spectrum_shape_id,
)

__all__ = (
    "ANIMATION_BEHAVIOR_CATALOG",
    "ANIMATION_BEHAVIOR_COUNT",
    "ANIMATION_BEHAVIOR_IDS",
    "COLOR_PALETTE_CATALOG",
    "COLOR_PALETTE_COUNT",
    "COLOR_PALETTE_IDS",
    "PARTICLE_TYPE_CATALOG",
    "PARTICLE_TYPE_COUNT",
    "PARTICLE_TYPE_IDS",
    "SPECTRUM_MATERIAL_CATALOG",
    "SPECTRUM_MATERIAL_COUNT",
    "SPECTRUM_MATERIAL_IDS",
    "SPECTRUM_SHAPE_CATALOG",
    "SPECTRUM_SHAPE_COUNT",
    "SPECTRUM_SHAPE_IDS",
    "build_shape_layers",
    "get_material",
    "get_palette",
    "get_particle_type",
    "list_animation_behavior_options",
    "list_color_palette_options",
    "list_particle_type_options",
    "list_spectrum_material_options",
    "list_spectrum_shape_options",
    "normalize_animation_behavior_id",
    "normalize_color_palette_id",
    "normalize_particle_type_id",
    "normalize_spectrum_material_id",
    "normalize_spectrum_shape_id",
)
