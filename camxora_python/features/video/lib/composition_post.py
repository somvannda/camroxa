"""Post-processing catalog (20) — whole-frame only (not spectrum)."""

from __future__ import annotations

from typing import Any

_POST_ROWS: tuple[tuple[str, str], ...] = (
    ("bloom", "Bloom"),
    ("color_grading", "Color Grading"),
    ("tone_mapping", "Tone Mapping"),
    ("hdr", "HDR"),
    ("exposure", "Exposure"),
    ("gamma", "Gamma"),
    ("contrast", "Contrast"),
    ("saturation", "Saturation"),
    ("vignette", "Vignette"),
    ("chromatic_aberration", "Chromatic Aberration"),
    ("film_grain", "Film Grain"),
    ("sharpen", "Sharpen"),
    ("motion_blur", "Motion Blur"),
    ("depth_of_field", "Depth of Field"),
    ("lens_distortion", "Lens Distortion"),
    ("glow", "Glow"),
    ("letterbox", "Letterbox"),
    ("posterize", "Posterize"),
    ("rgb_split", "RGB Split"),
    ("soft_diffusion", "Soft Diffusion"),
)

POST_EFFECT_CATALOG: tuple[dict[str, str], ...] = tuple(
    {"id": row[0], "label": row[1]} for row in _POST_ROWS
)
POST_EFFECT_IDS: frozenset[str] = frozenset(item["id"] for item in POST_EFFECT_CATALOG)
POST_EFFECT_COUNT = len(POST_EFFECT_CATALOG)
assert POST_EFFECT_COUNT == 20, POST_EFFECT_COUNT

_ALIASES: dict[str, str] = {
    **{item["id"]: item["id"] for item in POST_EFFECT_CATALOG},
    **{item["label"].lower(): item["id"] for item in POST_EFFECT_CATALOG},
    "color grading": "color_grading",
    "tone mapping": "tone_mapping",
    "chromatic aberration": "chromatic_aberration",
    "film grain": "film_grain",
    "motion blur": "motion_blur",
    "depth of field": "depth_of_field",
    "lens distortion": "lens_distortion",
    "rgb split": "rgb_split",
    "soft diffusion": "soft_diffusion",
}


def list_post_effect_options() -> tuple[tuple[str, str], ...]:
    return tuple((item["id"], item["label"]) for item in POST_EFFECT_CATALOG)


def normalize_post_effect_id(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "none":
        return None
    compact = raw.replace(" ", "_").replace("-", "_")
    if compact in POST_EFFECT_IDS:
        return compact
    spaced = raw.replace("_", " ").replace("-", " ")
    if spaced in _ALIASES:
        return _ALIASES[spaced]
    if raw in _ALIASES:
        return _ALIASES[raw]
    return None


def normalize_post_effects_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        eid = normalize_post_effect_id(value)
        if eid and eid not in seen:
            seen.add(eid)
            out.append(eid)
    return out
