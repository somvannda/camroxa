"""Animation preset metadata + preview asset resolution.

Drop GIF/WebP loops into ``assets/animations/{preset_id}.gif`` for CapCut-style
hover previews. Without a file, cards show a tinted Lucide icon.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "animations"


@dataclass(frozen=True)
class AnimationPresetInfo:
    id: str
    name: str
    category: str
    icon: str
    swatch_from: str
    swatch_to: str


def animation_preview_path(preset_id: str) -> Path | None:
    if preset_id == "none":
        return None
    for ext in (".gif", ".webp"):
        path = _ASSETS_DIR / f"{preset_id}{ext}"
        if path.is_file():
            return path
    return None


ANIMATION_PRESETS: list[AnimationPresetInfo] = [
    AnimationPresetInfo("none", "None", "in", "circle-slash", "#444444", "#666666"),
    AnimationPresetInfo("flash-in", "Flash In", "in", "sparkles", "#ff5470", "#ffb648"),
    AnimationPresetInfo("zoom-in", "Zoom In", "in", "zoom-in", "#7c5cff", "#a855f7"),
    AnimationPresetInfo("fade-in", "Fade In", "in", "sunrise", "#5cc9ff", "#7c5cff"),
    AnimationPresetInfo("slide-in", "Slide In", "in", "move-right", "#26d6a4", "#5cc9ff"),
    AnimationPresetInfo("unfold", "Unfold", "in", "maximize-2", "#ffb648", "#ff5470"),
    AnimationPresetInfo("jelly-in", "Jelly In", "in", "sparkles", "#ff9ad5", "#7c5cff"),
    AnimationPresetInfo("none", "None", "out", "circle-slash", "#444444", "#666666"),
    AnimationPresetInfo("flash-out", "Flash Out", "out", "sparkles", "#ffb648", "#ff5470"),
    AnimationPresetInfo("zoom-out", "Zoom Out", "out", "zoom-out", "#a855f7", "#7c5cff"),
    AnimationPresetInfo("fade-out", "Fade Out", "out", "sunset", "#7c5cff", "#5cc9ff"),
    AnimationPresetInfo("slide-out", "Slide Out", "out", "move-left", "#5cc9ff", "#26d6a4"),
    AnimationPresetInfo("none", "None", "combo", "circle-slash", "#444444", "#666666"),
    AnimationPresetInfo("pulse", "Pulse", "combo", "activity", "#ff5470", "#ffb648"),
    AnimationPresetInfo("shake", "Shake", "combo", "vibrate", "#7c5cff", "#ff5470"),
    AnimationPresetInfo("bounce", "Bounce", "combo", "arrow-up-down", "#26d6a4", "#5cc9ff"),
    AnimationPresetInfo("spin", "Spin", "combo", "rotate-cw", "#ffb648", "#7c5cff"),
    AnimationPresetInfo("none", "None", "audio", "circle-slash", "#444444", "#666666"),
    AnimationPresetInfo("pulse-beat", "Pulse to Beat", "audio", "audio-lines", "#ff5470", "#7c5cff"),
    AnimationPresetInfo("scale-bass", "Scale to Bass", "audio", "volume-2", "#26d6a4", "#5cc9ff"),
    AnimationPresetInfo("shake-hit", "Shake on Hit", "audio", "vibrate", "#ffb648", "#ff5470"),
    AnimationPresetInfo("glow-peak", "Glow on Peak", "audio", "sparkles", "#5cc9ff", "#a855f7"),
    AnimationPresetInfo("bounce-rhythm", "Bounce to Rhythm", "audio", "music-2", "#ff9ad5", "#7c5cff"),
]

PRESETS_BY_CATEGORY: dict[str, list[AnimationPresetInfo]] = {}
for preset in ANIMATION_PRESETS:
    PRESETS_BY_CATEGORY.setdefault(preset.category, []).append(preset)
