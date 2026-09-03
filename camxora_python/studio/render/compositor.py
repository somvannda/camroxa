"""Frame compositor — the single `render_frame()` used by both the live
preview and the export pipeline (guaranteeing preview/export parity).

Port of the reference app's `render(time)` / `activeClipsAt()` /
`computeOpacity()` / `drawContain()`.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np
from PySide6.QtGui import QImage

from studio.core.models import Clip, Track
from studio.core.project_state import ProjectState
from studio.core.registries import VIZ_STYLES_BY_ID
from studio.core.time_utils import clamp
from studio.media.audio_source import AudioSourceCache
from studio.media.video_source import VideoSourceCache
from studio.render.clip_geometry import apply_crop, clip_dest_rect
from studio.render.filters import apply_filter
from studio.render.mask import apply_crop_alpha, build_clip_mask
from studio.render.text_renderer import draw_text_overlay
from studio.render.visualizer import draw_visualizer

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
BACKGROUND_COLOR = (10, 10, 15)

logger = logging.getLogger(__name__)

_image_cache: dict[str, np.ndarray | None] = {}
_image_alpha_cache: dict[str, np.ndarray | None] = {}
_filtered_image_cache: dict[str, np.ndarray] = {}


def clear_image_cache() -> None:
    _image_cache.clear()
    _image_alpha_cache.clear()
    _filtered_image_cache.clear()


def _filter_cache_key(path: str, clip: Clip) -> str:
    return f"{path}:{clip.filter}"


def _filtered_image(path: str, clip: Clip) -> np.ndarray | None:
    frame = _load_image_rgb(path)
    if frame is None:
        return None
    if clip.filter == "none":
        return frame
    key = _filter_cache_key(path, clip)
    if key not in _filtered_image_cache:
        _filtered_image_cache[key] = apply_filter(frame, clip.filter)
    return _filtered_image_cache[key]


def _load_image_rgb(path: str) -> np.ndarray | None:
    if path not in _image_cache:
        frame = cv2.imread(path, cv2.IMREAD_COLOR)
        _image_cache[path] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame is not None else None
    return _image_cache[path]


def _load_image_rgba(path: str) -> tuple[np.ndarray | None, np.ndarray | None]:
    if path not in _image_cache:
        raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            _image_cache[path] = None
            _image_alpha_cache[path] = None
        elif raw.ndim == 3 and raw.shape[2] == 4:
            bgr = raw[:, :, :3]
            _image_cache[path] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            _image_alpha_cache[path] = raw[:, :, 3].astype(np.float32) / 255.0
        else:
            if raw.ndim == 2:
                raw = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
            _image_cache[path] = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
            _image_alpha_cache[path] = None
    return _image_cache.get(path), _image_alpha_cache.get(path)


def _blit_rgb(canvas: np.ndarray, patch: np.ndarray, x0: int, y0: int, opacity: float) -> None:
    """Blit ``patch`` onto ``canvas`` at top-left ``(x0, y0)``, clipped to canvas bounds."""
    _blit_with_alpha(canvas, patch, None, x0, y0, opacity)


def _blit_with_alpha(
    canvas: np.ndarray,
    patch: np.ndarray,
    alpha_mask: np.ndarray | None,
    x0: int,
    y0: int,
    opacity: float,
) -> None:
    if opacity <= 0.0:
        return
    canvas_h, canvas_w = canvas.shape[:2]
    src_h, src_w = patch.shape[:2]
    if src_w <= 0 or src_h <= 0:
        return

    dst_x1 = max(0, x0)
    dst_y1 = max(0, y0)
    dst_x2 = min(canvas_w, x0 + src_w)
    dst_y2 = min(canvas_h, y0 + src_h)
    if dst_x2 <= dst_x1 or dst_y2 <= dst_y1:
        return

    src_x1 = dst_x1 - x0
    src_y1 = dst_y1 - y0
    src_x2 = src_x1 + (dst_x2 - dst_x1)
    src_y2 = src_y1 + (dst_y2 - dst_y1)
    region = canvas[dst_y1:dst_y2, dst_x1:dst_x2].astype(np.float32)
    tile = patch[src_y1:src_y2, src_x1:src_x2].astype(np.float32)

    if alpha_mask is not None:
        alpha = alpha_mask[src_y1:src_y2, src_x1:src_x2].astype(np.float32) * opacity
        alpha = alpha[..., np.newaxis]
    else:
        alpha = opacity

    blended = region * (1.0 - alpha) + tile * alpha
    canvas[dst_y1:dst_y2, dst_x1:dst_x2] = blended.astype(np.uint8)


def _draw_visual_clip(
    canvas: np.ndarray,
    frame: np.ndarray,
    clip: Clip,
    opacity: float,
    source_alpha: np.ndarray | None = None,
) -> None:
    """Draw an image/video frame with per-clip scale, position, and crop."""
    if opacity <= 0.0:
        return
    cropped = apply_crop(frame, clip)
    if source_alpha is not None:
        source_alpha = apply_crop_alpha(source_alpha, clip)
    canvas_h, canvas_w = canvas.shape[:2]
    src_h, src_w = cropped.shape[:2]
    if src_w <= 0 or src_h <= 0:
        return

    x0, y0, dst_w, dst_h = clip_dest_rect(clip, src_w, src_h, canvas_w, canvas_h)
    if dst_w <= 0 or dst_h <= 0:
        logger.warning(
            "draw_visual skip clip=%s fit=%s zero dest %sx%s",
            clip.id,
            clip.fit_mode,
            dst_w,
            dst_h,
        )
        return
    try:
        scale = dst_w / src_w if src_w > 0 else 1.0
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        resized = cv2.resize(cropped, (dst_w, dst_h), interpolation=interp)

        alpha_mask = build_clip_mask(clip, dst_w, dst_h)
        if source_alpha is not None:
            src_alpha = cv2.resize(source_alpha, (dst_w, dst_h), interpolation=interp)
            alpha_mask = alpha_mask * src_alpha

        _blit_with_alpha(canvas, resized, alpha_mask, x0, y0, opacity)
    except Exception:
        logger.exception(
            "draw_visual failed clip=%s fit=%s src=%sx%s dst=%sx%s canvas=%sx%s",
            clip.id,
            clip.fit_mode,
            src_w,
            src_h,
            dst_w,
            dst_h,
            canvas_w,
            canvas_h,
        )
        raise


def _draw_contain(canvas: np.ndarray, frame: np.ndarray, opacity: float) -> None:
    """Legacy contain-fit blit — used when no clip transform context is available."""
    if opacity <= 0.0:
        return
    canvas_h, canvas_w = canvas.shape[:2]
    src_h, src_w = frame.shape[:2]
    if src_w <= 0 or src_h <= 0:
        return
    scale = min(canvas_w / src_w, canvas_h / src_h)
    dst_w = max(1, int(round(src_w * scale)))
    dst_h = max(1, int(round(src_h * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(frame, (dst_w, dst_h), interpolation=interp)
    x0 = (canvas_w - dst_w) // 2
    y0 = (canvas_h - dst_h) // 2
    _blit_rgb(canvas, resized, x0, y0, opacity)


def _track_z_index(project_state: ProjectState) -> dict[str, int]:
    return {track.id: index for index, track in enumerate(project_state.project.tracks)}


def render_frame(
    project_state: ProjectState,
    time: float,
    video_cache: VideoSourceCache,
    audio_cache: AudioSourceCache | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> np.ndarray:
    """Composite video + overlay + visualizer layers at `time` into an
    HxWx3 uint8 RGB array. `audio_cache` is optional — pass one to enable
    the music visualizer overlay for active audio clips with `viz_enabled`."""
    canvas = np.full((height, width, 3), BACKGROUND_COLOR, dtype=np.uint8)
    active = project_state.active_clips_at(time)
    track_z = _track_z_index(project_state)

    visual_layers: list[tuple[int, Track, Clip]] = []
    for track, clip in active.video:
        visual_layers.append((track_z.get(track.id, 0), track, clip))
    for track, clip in active.overlay:
        visual_layers.append((track_z.get(track.id, 0), track, clip))
    # Higher timeline rows (lower index) must paint last so they appear on top.
    visual_layers.sort(key=lambda item: item[0], reverse=True)

    for _z, track, clip in visual_layers:
        if clip.kind == "image":
            media = project_state.get_media(clip.media_id)
            if media is None:
                continue
            use_nobg = clip.remove_bg_enabled and media.remove_bg_path
            if use_nobg:
                frame, source_alpha = _load_image_rgba(media.remove_bg_path)
                if frame is None:
                    continue
                if clip.filter != "none":
                    frame = apply_filter(frame, clip.filter)
            else:
                frame = _filtered_image(media.path, clip)
                source_alpha = None
                if frame is None:
                    continue
            opacity = clamp(ProjectState.compute_opacity(clip, time), 0.0, 1.0)
            _draw_visual_clip(canvas, frame, clip, opacity, source_alpha)
        elif clip.kind == "video":
            media = project_state.get_media(clip.media_id)
            if media is None or media.type != "video":
                continue
            source = video_cache.get(media.id, media.path)
            local_time = (time - clip.start) + clip.trim_start
            frame = source.get_frame_rgb(local_time)
            if frame is None:
                continue
            frame = apply_filter(frame, clip.filter)
            opacity = clamp(ProjectState.compute_opacity(clip, time), 0.0, 1.0)
            _draw_visual_clip(canvas, frame, clip, opacity)
        elif clip.kind == "text":
            opacity = clamp(ProjectState.compute_opacity(clip, time), 0.0, 1.0)
            draw_text_overlay(canvas, clip, opacity)
        elif clip.kind == "playlist":
            from studio.render.playlist_renderer import draw_playlist_foreground

            draw_playlist_foreground(canvas, project_state, time, audio_cache=audio_cache)

    if audio_cache is not None:
        for _track, clip in active.audio:
            if not clip.viz_enabled:
                continue
            media = project_state.get_media(clip.media_id)
            if media is None:
                continue
            source = audio_cache.get(media.id, media.path, media.type)
            if source is None:
                continue
            local_time = (time - clip.start) + clip.trim_start
            style_info = VIZ_STYLES_BY_ID.get(clip.viz)
            if style_info is None:
                continue
            band_values = source.get_spectrum_bands(local_time)
            wave_values = source.get_waveform_samples(local_time)
            opacity = clamp(clip.opacity if clip.opacity is not None else 1.0, 0.0, 1.0)
            draw_visualizer(canvas, clip.viz, band_values, wave_values, style_info.swatch_from, style_info.swatch_to, opacity)

    if getattr(project_state, "playlist_preview_active", False):
        from studio.core.playlist_scene_sync import SCENE_BACKGROUND, find_scene_track, has_playlist_scene
        from studio.render.playlist_renderer import draw_playlist, draw_playlist_background

        if not has_playlist_scene(project_state.project):
            draw_playlist(canvas, project_state, time, audio_cache=audio_cache)
        else:
            bg_track = find_scene_track(project_state.project, SCENE_BACKGROUND)
            has_bg_clip = bg_track is not None and any(c.kind == "image" for c in bg_track.clips)
            if not has_bg_clip:
                draw_playlist_background(canvas, project_state)

    return canvas


def frame_to_qimage(frame: np.ndarray) -> QImage:
    """Convert an HxWx3 uint8 RGB numpy array to a QImage (copies the data
    so the QImage stays valid after the numpy array is reused/freed)."""
    frame = np.ascontiguousarray(frame)
    h, w, _ = frame.shape
    image = QImage(frame.data, w, h, frame.strides[0], QImage.Format.Format_RGB888)
    return image.copy()
