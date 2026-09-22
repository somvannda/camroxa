"""Sync playlist preview scene (background + card UI + audio) onto the timeline."""

from __future__ import annotations

from pathlib import Path

from studio.core.models import Clip, MediaAsset, Track, new_id
from studio.core.playlist_assets import resolve_playlist_background
from studio.core.project_state import ProjectState, normalize_media_path

SCENE_BACKGROUND = "playlist_background"
SCENE_GRAPHICS = "playlist_graphics"
SCENE_AUDIO = "playlist_audio"

_BACKGROUND_TRACK_NAME = "Background"
_GRAPHICS_TRACK_NAME = "Playlist"
_AUDIO_TRACK_NAME = "Playlist"


def find_scene_track(project, scene_role: str) -> Track | None:
    return next((t for t in project.tracks if t.scene_role == scene_role), None)


def has_playlist_scene(project) -> bool:
    return any(t.scene_role for t in project.tracks)


def playlist_content_duration(state: ProjectState) -> float:
    """Total duration spanned by playlist songs (minimum 1s for empty previews)."""
    total = 0.0
    for media_id in state.project.playlist.song_ids:
        media = state.get_media(media_id)
        if media is None or media.type != "audio":
            continue
        duration = float(media.duration or 0.0)
        if duration > 0:
            total += duration
    return max(total, 1.0)


def _ensure_image_media(state: ProjectState, path: str) -> MediaAsset | None:
    existing = state.find_media_by_path(path)
    if existing is not None:
        return existing
    resolved = Path(path)
    if not resolved.is_file():
        return None
    media = MediaAsset(
        id=new_id("media"),
        name=resolved.stem or "Background",
        type="image",
        path=str(resolved.resolve()),
        duration=0.0,
    )
    state.add_media(media)
    return media


def _find_or_create_scene_track(
    state: ProjectState,
    *,
    scene_role: str,
    track_type: str,
    name: str,
) -> Track:
    track = find_scene_track(state.project, scene_role)
    if track is not None:
        track.name = name
        track.locked = True
        return track
    track = Track(
        id=new_id("trk"),
        type=track_type,  # type: ignore[arg-type]
        name=name,
        locked=True,
        scene_role=scene_role,
    )
    state.project.tracks.append(track)
    return track


def _upsert_scene_clip(
    track: Track,
    *,
    scene_role: str,
    kind: str,
    label: str,
    duration: float,
    media_id: str | None = None,
    fit_mode: str = "free",
) -> Clip:
    clip = next((c for c in track.clips if c.scene_role == scene_role), None)
    if clip is None:
        clip = Clip(
            id=new_id("clip"),
            track_id=track.id,
            kind=kind,  # type: ignore[arg-type]
            label=label,
            start=0.0,
            duration=duration,
            scene_role=scene_role,
            fit_mode=fit_mode,
        )
        track.clips.append(clip)
    clip.track_id = track.id
    clip.kind = kind  # type: ignore[assignment]
    clip.label = label
    clip.start = 0.0
    clip.duration = duration
    clip.scene_role = scene_role
    clip.media_id = media_id
    clip.fit_mode = fit_mode
    if kind == "image":
        clip.transform_scale = 1.0
        clip.transform_x = 0.5
        clip.transform_y = 0.5
        clip.fit_mode = "cover"
    return clip


def _reorder_scene_tracks(state: ProjectState) -> None:
    """Stack order for compositor: lower index paints on top.

    Playlist card (front) → user video/overlay → background (back) → audio rows.
    """
    tracks = state.project.tracks
    background = [t for t in tracks if t.scene_role == SCENE_BACKGROUND]
    graphics = [t for t in tracks if t.scene_role == SCENE_GRAPHICS]
    audio = [t for t in tracks if t.scene_role == SCENE_AUDIO]
    user = [t for t in tracks if not t.scene_role]
    user_visual = [t for t in user if t.type in ("video", "overlay")]
    user_audio = [t for t in user if t.type == "audio"]
    state.project.tracks = graphics + user_visual + background + user_audio + audio


def sync_playlist_scene_to_timeline(state: ProjectState, *, record_undo: bool = False) -> None:
    """Ensure managed background, playlist card, and audio rows reflect playlist settings."""
    settings = state.project.playlist
    if not settings.template_id:
        return

    if record_undo:
        state._push_undo()

    duration = playlist_content_duration(state)

    bg_track = _find_or_create_scene_track(
        state,
        scene_role=SCENE_BACKGROUND,
        track_type="video",
        name=_BACKGROUND_TRACK_NAME,
    )
    gfx_track = _find_or_create_scene_track(
        state,
        scene_role=SCENE_GRAPHICS,
        track_type="overlay",
        name=_GRAPHICS_TRACK_NAME,
    )

    bg_path_obj = resolve_playlist_background(settings)
    bg_media_id: str | None = None
    if bg_path_obj is not None and bg_path_obj.is_file():
        media = _ensure_image_media(state, str(bg_path_obj))
        if media is not None:
            bg_media_id = media.id

    if bg_media_id is not None:
        _upsert_scene_clip(
            bg_track,
            scene_role=SCENE_BACKGROUND,
            kind="image",
            label="Scene background",
            duration=duration,
            media_id=bg_media_id,
            fit_mode="cover",
        )
    else:
        bg_track.clips = [c for c in bg_track.clips if c.scene_role != SCENE_BACKGROUND]

    _upsert_scene_clip(
        gfx_track,
        scene_role=SCENE_GRAPHICS,
        kind="playlist",
        label="Playlist card",
        duration=duration,
    )

    _reorder_scene_tracks(state)
    state.recalc_duration()
