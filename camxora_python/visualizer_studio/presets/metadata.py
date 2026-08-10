"""Asset library metadata for composition catalogs (doc 08 knowledge base).

Catalogs stay id/label authoritative for compile. Metadata is additive for
Studio Asset Library search and future AI Designer ranking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from visualizer_studio.presets.animations import ANIMATION_BEHAVIOR_CATALOG
from visualizer_studio.presets.atmosphere import ATMOSPHERE_CATALOG
from visualizer_studio.presets.audio_buses import AUDIO_BUS_CATALOG
from visualizer_studio.presets.background_motion import BACKGROUND_MOTION_CATALOG
from visualizer_studio.presets.camera import CAMERA_BEHAVIOR_CATALOG
from visualizer_studio.presets.lighting import LIGHTING_EFFECT_CATALOG
from visualizer_studio.presets.materials import SPECTRUM_MATERIAL_CATALOG
from visualizer_studio.presets.palettes import COLOR_PALETTE_CATALOG
from visualizer_studio.presets.particles import PARTICLE_TYPE_CATALOG
from visualizer_studio.presets.post import POST_EFFECT_CATALOG
from visualizer_studio.presets.shapes import SPECTRUM_SHAPE_CATALOG

PerformanceTier = str  # "low" | "medium" | "high"


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    id: str
    category: str
    name: str
    tags: tuple[str, ...] = ()
    mood: tuple[str, ...] = ()
    genre: tuple[str, ...] = ()
    theme: tuple[str, ...] = ()
    performance: PerformanceTier = "low"
    recommended: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    ai_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ASSET_CATEGORIES: tuple[str, ...] = (
    "palette",
    "shape",
    "material",
    "animation",
    "particle",
    "lighting",
    "camera",
    "atmosphere",
    "background_motion",
    "post",
    "audio_bus",
)

# Curated overrides (id -> partial fields). Unspecified fields use heuristics.
_OVERRIDES: dict[str, dict[str, Any]] = {
    "neon": {
        "tags": ("EDM", "Cyberpunk", "Glow"),
        "mood": ("Energetic",),
        "genre": ("EDM", "Synthwave"),
        "theme": ("Cyberpunk", "Festival"),
        "performance": "low",
        "recommended": ("lightning", "bloom", "cyberpunk"),
        "ai_description": "Bright neon material for cyberpunk / festival spectrums.",
    },
    "lightning": {
        "tags": ("Bass", "Impact", "EDM"),
        "mood": ("Aggressive", "Energetic"),
        "genre": ("EDM", "Dubstep"),
        "theme": ("Festival", "Cyberpunk"),
        "performance": "medium",
        "recommended": ("neon", "bass", "bloom"),
        "avoid": ("soft_diffusion",),
        "ai_description": "Bass-triggered lightning bolts for high-energy drops.",
    },
    "fog": {
        "tags": ("Atmosphere", "Cinematic"),
        "mood": ("Dark", "Dreamy"),
        "theme": ("Night Drive", "Galaxy"),
        "performance": "medium",
        "avoid": ("rain", "heavy particles"),
        "ai_description": "Soft volumetric fog for cinematic depth.",
    },
    "cyberpunk": {
        "tags": ("Purple", "Cyan", "Neon"),
        "mood": ("Energetic",),
        "genre": ("EDM", "Synthwave"),
        "theme": ("Cyberpunk",),
        "ai_description": "Purple/cyan cyberpunk color palette.",
    },
    "shake": {
        "tags": ("Impact", "Bass"),
        "mood": ("Aggressive",),
        "genre": ("EDM", "Trap"),
        "performance": "low",
        "recommended": ("kick", "bass"),
        "ai_description": "Camera shake for bass hits and drops.",
    },
    "bloom": {
        "tags": ("Glow", "Cinematic"),
        "mood": ("Epic",),
        "theme": ("Festival", "Cyberpunk"),
        "performance": "medium",
        "recommended": ("neon", "glow"),
        "ai_description": "Whole-frame bloom for neon and festival looks.",
    },
    "circle": {
        "tags": ("Classic", "Logo-centric"),
        "mood": ("Energetic",),
        "genre": ("EDM", "Pop"),
        "theme": ("Festival",),
        "ai_description": "Classic circular spectrum around a logo.",
    },
    "sparkles": {
        "tags": ("Magic", "Bright"),
        "mood": ("Dreamy", "Energetic"),
        "performance": "medium",
        "recommended": ("neon", "pulse"),
        "ai_description": "Bright sparkle particle emitter for accents.",
    },
}


def _heuristic(
    *,
    asset_id: str,
    category: str,
    name: str,
) -> AssetMetadata:
    override = _OVERRIDES.get(asset_id, {})
    tags = tuple(override.get("tags") or (category.title(), name))
    mood = tuple(override.get("mood") or ("Energetic",))
    genre = tuple(override.get("genre") or ("EDM",))
    theme = tuple(override.get("theme") or ("Festival",))
    performance = str(override.get("performance") or "low")
    recommended = tuple(override.get("recommended") or ())
    avoid = tuple(override.get("avoid") or ())
    ai_description = str(
        override.get("ai_description")
        or f"{name} ({category}) reusable composition asset."
    )
    return AssetMetadata(
        id=asset_id,
        category=category,
        name=name,
        tags=tags,
        mood=mood,
        genre=genre,
        theme=theme,
        performance=performance if performance in {"low", "medium", "high"} else "low",
        recommended=recommended,
        avoid=avoid,
        ai_description=ai_description,
    )


def _from_catalog(category: str, catalog: Iterable[dict[str, Any]]) -> tuple[AssetMetadata, ...]:
    rows: list[AssetMetadata] = []
    for item in catalog:
        asset_id = str(item.get("id") or "").strip()
        name = str(item.get("label") or item.get("name") or asset_id).strip()
        if not asset_id:
            continue
        rows.append(_heuristic(asset_id=asset_id, category=category, name=name))
    return tuple(rows)


def all_asset_metadata() -> tuple[AssetMetadata, ...]:
    return (
        *_from_catalog("palette", COLOR_PALETTE_CATALOG),
        *_from_catalog("shape", SPECTRUM_SHAPE_CATALOG),
        *_from_catalog("material", SPECTRUM_MATERIAL_CATALOG),
        *_from_catalog("animation", ANIMATION_BEHAVIOR_CATALOG),
        *_from_catalog("particle", PARTICLE_TYPE_CATALOG),
        *_from_catalog("lighting", LIGHTING_EFFECT_CATALOG),
        *_from_catalog("camera", CAMERA_BEHAVIOR_CATALOG),
        *_from_catalog("atmosphere", ATMOSPHERE_CATALOG),
        *_from_catalog("background_motion", BACKGROUND_MOTION_CATALOG),
        *_from_catalog("post", POST_EFFECT_CATALOG),
        *_from_catalog("audio_bus", AUDIO_BUS_CATALOG),
    )


def get_asset_metadata(asset_id: str, *, category: str | None = None) -> AssetMetadata | None:
    needle = str(asset_id or "").strip().lower()
    if not needle:
        return None
    for item in all_asset_metadata():
        if item.id != needle:
            continue
        if category and item.category != category:
            continue
        return item
    return None


def search_assets(
    *,
    query: str = "",
    category: str | None = None,
    mood: str | None = None,
    genre: str | None = None,
    theme: str | None = None,
    performance: str | None = None,
) -> tuple[AssetMetadata, ...]:
    q = str(query or "").strip().lower()
    out: list[AssetMetadata] = []
    for item in all_asset_metadata():
        if category and item.category != category:
            continue
        if mood and mood not in item.mood:
            continue
        if genre and genre not in item.genre:
            continue
        if theme and theme not in item.theme:
            continue
        if performance and item.performance != performance:
            continue
        if q:
            hay = " ".join(
                [
                    item.id,
                    item.name,
                    item.category,
                    " ".join(item.tags),
                    " ".join(item.mood),
                    " ".join(item.genre),
                    " ".join(item.theme),
                    item.ai_description,
                ]
            ).lower()
            if q not in hay:
                continue
        out.append(item)
    return tuple(out)


def asset_metadata_index() -> dict[str, AssetMetadata]:
    """Map asset id → first matching metadata (unique ids across categories)."""
    index: dict[str, AssetMetadata] = {}
    for item in all_asset_metadata():
        index.setdefault(item.id, item)
    return index
