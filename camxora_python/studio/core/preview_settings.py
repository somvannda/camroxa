"""Preview canvas aspect ratios and playback render quality presets."""

from __future__ import annotations

from dataclasses import dataclass

from studio.core.models import MediaAsset, Project

CANVAS_BASE = 720


@dataclass(frozen=True)
class AspectRatioPreset:
    id: str
    label: str
    width: int
    height: int
    icon: str  # shape hint for menu icon


@dataclass(frozen=True)
class PreviewQualityPreset:
    id: str
    label: str
    scale: float | None  # None = auto


ASPECT_RATIO_PRESETS: tuple[AspectRatioPreset, ...] = (
    AspectRatioPreset("16:9", "16:9", 1280, 720, "landscape"),
    AspectRatioPreset("4:3", "4:3", 960, 720, "landscape"),
    AspectRatioPreset("2.35:1", "2.35:1", 1692, 720, "ultrawide"),
    AspectRatioPreset("2:1", "2:1", 1440, 720, "wide"),
    AspectRatioPreset("1.85:1", "1.85:1", 1332, 720, "wide"),
    AspectRatioPreset("9:16", "9:16", 720, 1280, "portrait"),
    AspectRatioPreset("3:4", "3:4", 720, 960, "portrait"),
    AspectRatioPreset("5.8-inch", "5.8-inch", 720, 1560, "phone"),
    AspectRatioPreset("1:1", "1:1", 720, 720, "square"),
)

PREVIEW_QUALITY_PRESETS: tuple[PreviewQualityPreset, ...] = (
    PreviewQualityPreset("full", "Full", 1.0),
    PreviewQualityPreset("half", "1/2", 0.5),
    PreviewQualityPreset("quarter", "1/4", 0.25),
    PreviewQualityPreset("eighth", "1/8", 0.125),
    PreviewQualityPreset("auto", "Auto", None),
)

_ASPECT_BY_ID = {p.id: p for p in ASPECT_RATIO_PRESETS}
_QUALITY_BY_ID = {p.id: p for p in PREVIEW_QUALITY_PRESETS}


def _even(value: int) -> int:
    return max(2, value - (value % 2))


def original_canvas_size(project: Project) -> tuple[int, int]:
    """First timeline media dimensions, else 16:9 HD."""
    media_by_id = {m.id: m for m in project.media_library}
    for track in project.tracks:
        for clip in track.clips:
            if clip.media_id and clip.media_id in media_by_id:
                media = media_by_id[clip.media_id]
                size = _media_canvas_size(media)
                if size is not None:
                    return size
    return 1280, 720


def _media_canvas_size(media: MediaAsset) -> tuple[int, int] | None:
    if media.width and media.height and media.width > 0 and media.height > 0:
        w, h = int(media.width), int(media.height)
        if w > 1920 or h > 1920:
            scale = min(1920 / w, 1920 / h)
            w = _even(int(w * scale))
            h = _even(int(h * scale))
        return _even(w), _even(h)
    return None


def canvas_size_for_project(project: Project) -> tuple[int, int]:
    preset_id = project.aspect_ratio_id
    if preset_id == "original":
        return original_canvas_size(project)
    preset = _ASPECT_BY_ID.get(preset_id)
    if preset is None:
        return project.canvas_width, project.canvas_height
    return preset.width, preset.height


def apply_aspect_ratio(project: Project, preset_id: str) -> tuple[int, int]:
    project.aspect_ratio_id = preset_id
    if preset_id == "custom":
        return project.canvas_width, project.canvas_height
    if preset_id == "original":
        w, h = original_canvas_size(project)
    else:
        preset = _ASPECT_BY_ID.get(preset_id)
        if preset is None:
            w, h = project.canvas_width, project.canvas_height
        else:
            w, h = preset.width, preset.height
    project.canvas_width = w
    project.canvas_height = h
    return w, h


def aspect_ratio_label(preset_id: str) -> str:
    if preset_id == "original":
        return "Original"
    if preset_id == "custom":
        return "Custom"
    preset = _ASPECT_BY_ID.get(preset_id)
    return preset.label if preset else preset_id


def preview_quality_label(quality_id: str) -> str:
    preset = _QUALITY_BY_ID.get(quality_id)
    return preset.label if preset else quality_id


def preview_render_size(
    canvas_w: int,
    canvas_h: int,
    quality_id: str,
    *,
    viewport_w: int | None = None,
    viewport_h: int | None = None,
    interactive: bool = False,
) -> tuple[int, int]:
    """Map quality preset to compositor output dimensions."""
    preset = _QUALITY_BY_ID.get(quality_id, _QUALITY_BY_ID["half"])
    if preset.scale is None:
        if viewport_w and viewport_h and viewport_w > 0 and viewport_h > 0:
            scale = min(viewport_w / canvas_w, viewport_h / canvas_h, 1.0)
        elif interactive:
            scale = min(480 / canvas_w, 270 / canvas_h, 1.0)
        else:
            scale = 1.0
    else:
        scale = preset.scale
    w = _even(int(canvas_w * scale))
    h = _even(int(canvas_h * scale))
    w = max(160, min(w, canvas_w))
    h = max(90, min(h, canvas_h))
    return w, h
