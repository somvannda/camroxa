from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SpectrumConfig:
    radius: float
    strength: float
    color: tuple[int, int, int]
    thickness: float
    point_count: int
    smoothing: float


@dataclass(frozen=True)
class TemplateConfig:
    background: str
    spectrum: SpectrumConfig


def _as_rgb(v: Any) -> tuple[int, int, int]:
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return (int(v[0]), int(v[1]), int(v[2]))
    if isinstance(v, str) and v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    return (255, 255, 255)


def load_template_v1(template_path: str) -> TemplateConfig:
    p = Path(template_path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    bg = str(raw.get("background", ""))
    spec = raw.get("spectrum") or {}

    radius = float(spec.get("radius", 240))
    strength = float(spec.get("strength", 120))
    color = _as_rgb(spec.get("color", [255, 255, 255]))
    thickness = float(spec.get("thickness", 4))
    point_count = int(spec.get("point_count", 256))
    smoothing = float(spec.get("smoothing", 0.8))

    return TemplateConfig(
        background=bg,
        spectrum=SpectrumConfig(
            radius=radius,
            strength=strength,
            color=color,
            thickness=thickness,
            point_count=point_count,
            smoothing=smoothing,
        ),
    )


def _as_vec2(v: Any) -> tuple[int, int]:
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return (int(v[0]), int(v[1]))
    return (0, 0)


def load_template_any(template_path: str) -> dict:
    p = Path(template_path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("layers"), list):
        return normalize_template_v2(raw)
    v1 = load_template_v1(template_path)
    return {
        "version": 2,
        "background": v1.background,
        "layers": [
            {"type": "background", "enabled": True, "z_index": 0, "opacity": 1.0, "blend_mode": "normal"},
            {
                "type": "spectrum",
                "enabled": True,
                "z_index": 10,
                "opacity": 1.0,
                "blend_mode": "normal",
                "analyzer": "default",
                "spectrum_layers": [
                    {
                        "type": "main",
                        "color": v1.spectrum.color,
                        "opacity": 1.0,
                        "thickness": v1.spectrum.thickness,
                        "blur": 0.0,
                        "radius_offset": 0.0,
                        "blend_mode": "normal",
                        "radius": v1.spectrum.radius,
                        "strength": v1.spectrum.strength,
                        "point_count": v1.spectrum.point_count,
                        "smoothing": v1.spectrum.smoothing,
                    }
                ],
            },
        ],
        "particles": {
            "enabled": False,
            "max_count": 800,
            "spawn_rate": 80.0,
            "lifetime_sec": 2.0,
            "size": 2.0,
            "opacity": 0.35,
            "color": (255, 255, 255),
            "speed": 120.0,
        },
        "effects": {
            "bloom": {"enabled": False, "strength": 1.0, "blur_radius": 11, "threshold": 0.75, "opacity": 0.9},
            "rgb_split": {
                "enabled": False,
                "red_offset": (2, 0),
                "green_offset": (0, 0),
                "blue_offset": (-2, 0),
                "opacity": 0.6,
            },
            "camera_shake": {"enabled": False, "intensity": 8.0, "smoothing": 0.85},
        },
        "analyzers": {
            "default": {"smoothing": 0.8, "sensitivity": 1.0},
        },
        "automations": [],
    }


def load_template_any_raw(raw: Any) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("layers"), list):
        return normalize_template_v2(raw)
    if isinstance(raw, dict):
        return normalize_template_v2(raw)
    raise ValueError("Template must be a JSON object")


def normalize_template_v2(raw: dict) -> dict:
    bg = str(raw.get("background", ""))
    bg_settings_raw = raw.get("background_settings") if isinstance(raw.get("background_settings"), dict) else {}
    logo_raw = raw.get("logo") if isinstance(raw.get("logo"), dict) else {}
    layers: list[dict] = []
    particles = raw.get("particles") if isinstance(raw.get("particles"), dict) else {}
    effects = raw.get("effects") if isinstance(raw.get("effects"), dict) else {}
    bloom = effects.get("bloom") if isinstance(effects.get("bloom"), dict) else {}
    rgb = effects.get("rgb_split") if isinstance(effects.get("rgb_split"), dict) else {}
    shake = effects.get("camera_shake") if isinstance(effects.get("camera_shake"), dict) else {}

    analyzers = raw.get("analyzers") if isinstance(raw.get("analyzers"), dict) else {}
    autos = raw.get("automations") if isinstance(raw.get("automations"), list) else []

    return {
        "version": 2,
        "background": bg,
        "background_settings": {
            "brightness": float(bg_settings_raw.get("brightness", 1.0)),
            "react_bass": float(bg_settings_raw.get("react_bass", 0.0)),
        },
        "logo": {
            "circle_mask": bool(logo_raw.get("circle_mask", True)),
            "opacity": float(logo_raw.get("opacity", 1.0)),
            "scale": float(logo_raw.get("scale", 1.0)),
            "react_bass": float(logo_raw.get("react_bass", 0.0)),
        },
        "layers": layers,
        "particles": {
            "enabled": bool(particles.get("enabled", False)),
            "max_count": int(particles.get("max_count", 800)),
            "spawn_rate": float(particles.get("spawn_rate", 80.0)),
            "react_bass": float(particles.get("react_bass", 0.0)),
            "lifetime_sec": float(particles.get("lifetime_sec", 2.0)),
            "size": float(particles.get("size", 2.0)),
            "opacity": float(particles.get("opacity", 0.35)),
            "color": _as_rgb(particles.get("color", [255, 255, 255])),
            "speed": float(particles.get("speed", 120.0)),
        },
        "effects": {
            "bloom": {
                "enabled": bool(bloom.get("enabled", False)),
                "strength": float(bloom.get("strength", 1.0)),
                "blur_radius": int(bloom.get("blur_radius", 11)),
                "threshold": float(bloom.get("threshold", 0.75)),
                "opacity": float(bloom.get("opacity", 0.9)),
            },
            "rgb_split": {
                "enabled": bool(rgb.get("enabled", False)),
                "red_offset": _as_vec2(rgb.get("red_offset", [2, 0])),
                "green_offset": _as_vec2(rgb.get("green_offset", [0, 0])),
                "blue_offset": _as_vec2(rgb.get("blue_offset", [-2, 0])),
                "opacity": float(rgb.get("opacity", 0.6)),
            },
            "camera_shake": {
                "enabled": bool(shake.get("enabled", False)),
                "intensity": float(shake.get("intensity", 8.0)),
                "smoothing": float(shake.get("smoothing", 0.85)),
            },
        },
        "analyzers": analyzers,
        "automations": autos,
    }
