"""Project data model: MediaAsset, Clip, Track, Project.

Ported from the reference app's `state` object (mediaLibrary, tracks with
clips). Kept JSON-serializable (to_dict/from_dict) so projects can be saved
and loaded, and so undo/redo can snapshot plain dicts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from studio.core.snap_models import SnapSettings, TimelineMarker
from studio.core.playlist_settings import PlaylistSettings
from studio.core.registries import FILTERS as _FILTER_REGISTRY

MediaType = Literal["video", "audio", "image", "text"]
TrackType = Literal["video", "audio", "overlay"]
ClipKind = Literal["video", "audio", "image", "text", "playlist"]
SceneRole = Literal["playlist_background", "playlist_graphics", "playlist_audio"]

FILTER_IDS = tuple(f.id for f in _FILTER_REGISTRY)
VIZ_IDS = ("bars", "mirror-bars", "wave", "circle")


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:9]}"


@dataclass
class MediaAsset:
    id: str
    name: str
    type: MediaType
    path: str
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    sample_rate: int | None = None
    thumb_path: str | None = None
    remove_bg_path: str | None = None  # cached PNG with alpha after background removal

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "path": self.path,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "sample_rate": self.sample_rate,
            "thumb_path": self.thumb_path,
            "remove_bg_path": self.remove_bg_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaAsset":
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            path=data["path"],
            duration=float(data.get("duration", 0.0)),
            width=data.get("width"),
            height=data.get("height"),
            sample_rate=data.get("sample_rate"),
            thumb_path=data.get("thumb_path"),
            remove_bg_path=data.get("remove_bg_path"),
        )


@dataclass
class Clip:
    id: str
    track_id: str
    kind: ClipKind
    label: str
    start: float
    duration: float
    media_id: str | None = None
    trim_start: float = 0.0
    trim_end: float = 0.0
    filter: str = "none"
    opacity: float = 1.0
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    viz: str = "bars"
    viz_enabled: bool = False
    # text-clip only fields
    text: str | None = None
    color: str | None = None
    size: float | None = None
    x: float | None = None
    y: float | None = None
    # image/video transform (normalized) — defaults reproduce letterboxed contain fit
    fit_mode: str = "free"  # free | fit | cover | fill
    transform_scale: float = 1.0
    transform_x: float = 0.5
    transform_y: float = 0.5
    crop_inset: float = 0.0  # 0..0.45 — uniform crop from each edge (fraction of source)
    remove_bg_enabled: bool = False
    # mask (relative to clip bounds, 0..1)
    mask_enabled: bool = False
    mask_shape: str = "rectangle"
    mask_x: float = 0.5
    mask_y: float = 0.5
    mask_width: float = 1.0
    mask_height: float = 1.0
    mask_rotation: float = 0.0
    mask_feather: float = 0.0  # 0..100
    mask_round_corners: float = 0.0  # 0..100
    mask_invert: bool = False
    # image-clip only
    thumb: str | None = None
    # video-clip only (list of thumbnail image paths for the filmstrip)
    thumb_cache: list[str] | None = None
    # audio-clip only (precomputed amplitude envelope for the timeline waveform)
    waveform_cache: list[float] | None = None
    linked_group_id: str | None = None
    scene_role: str | None = None  # managed playlist scene clip — not user-editable

    @property
    def end(self) -> float:
        return self.start + self.duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "track_id": self.track_id,
            "kind": self.kind,
            "label": self.label,
            "start": self.start,
            "duration": self.duration,
            "media_id": self.media_id,
            "trim_start": self.trim_start,
            "trim_end": self.trim_end,
            "filter": self.filter,
            "opacity": self.opacity,
            "volume": self.volume,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "viz": self.viz,
            "viz_enabled": self.viz_enabled,
            "text": self.text,
            "color": self.color,
            "size": self.size,
            "x": self.x,
            "y": self.y,
            "transform_scale": self.transform_scale,
            "fit_mode": self.fit_mode,
            "transform_x": self.transform_x,
            "transform_y": self.transform_y,
            "crop_inset": self.crop_inset,
            "remove_bg_enabled": self.remove_bg_enabled,
            "mask_enabled": self.mask_enabled,
            "mask_shape": self.mask_shape,
            "mask_x": self.mask_x,
            "mask_y": self.mask_y,
            "mask_width": self.mask_width,
            "mask_height": self.mask_height,
            "mask_rotation": self.mask_rotation,
            "mask_feather": self.mask_feather,
            "mask_round_corners": self.mask_round_corners,
            "mask_invert": self.mask_invert,
            "thumb": self.thumb,
            "thumb_cache": self.thumb_cache,
            "waveform_cache": self.waveform_cache,
            "linked_group_id": self.linked_group_id,
            "scene_role": self.scene_role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Clip":
        return cls(
            id=data["id"],
            track_id=data["track_id"],
            kind=data["kind"],
            label=data["label"],
            start=float(data["start"]),
            duration=float(data["duration"]),
            media_id=data.get("media_id"),
            trim_start=float(data.get("trim_start", 0.0)),
            trim_end=float(data.get("trim_end", 0.0)),
            filter=data.get("filter", "none"),
            opacity=float(data.get("opacity", 1.0)),
            volume=float(data.get("volume", 1.0)),
            fade_in=float(data.get("fade_in", 0.0)),
            fade_out=float(data.get("fade_out", 0.0)),
            viz=data.get("viz", "bars"),
            viz_enabled=bool(data.get("viz_enabled", False)),
            text=data.get("text"),
            color=data.get("color"),
            size=data.get("size"),
            x=data.get("x"),
            y=data.get("y"),
            transform_scale=float(data.get("transform_scale", 1.0)),
            fit_mode=str(data.get("fit_mode", "free")),
            transform_x=float(data.get("transform_x", 0.5)),
            transform_y=float(data.get("transform_y", 0.5)),
            crop_inset=float(data.get("crop_inset", 0.0)),
            remove_bg_enabled=bool(data.get("remove_bg_enabled", False)),
            mask_enabled=bool(data.get("mask_enabled", False)),
            mask_shape=str(data.get("mask_shape", "rectangle")),
            mask_x=float(data.get("mask_x", 0.5)),
            mask_y=float(data.get("mask_y", 0.5)),
            mask_width=float(data.get("mask_width", 1.0)),
            mask_height=float(data.get("mask_height", 1.0)),
            mask_rotation=float(data.get("mask_rotation", 0.0)),
            mask_feather=float(data.get("mask_feather", 0.0)),
            mask_round_corners=float(data.get("mask_round_corners", 0.0)),
            mask_invert=bool(data.get("mask_invert", False)),
            thumb=data.get("thumb"),
            thumb_cache=data.get("thumb_cache"),
            waveform_cache=data.get("waveform_cache"),
            linked_group_id=data.get("linked_group_id"),
            scene_role=data.get("scene_role"),
        )


@dataclass
class Track:
    id: str
    type: TrackType
    name: str
    clips: list[Clip] = field(default_factory=list)
    muted: bool = False
    hidden: bool = False
    locked: bool = False
    solo: bool = False
    scene_role: str | None = None  # managed playlist scene track

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
            "hidden": self.hidden,
            "locked": self.locked,
            "solo": self.solo,
            "scene_role": self.scene_role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Track":
        return cls(
            id=data["id"],
            type=data["type"],
            name=data["name"],
            clips=[Clip.from_dict(c) for c in data.get("clips", [])],
            muted=bool(data.get("muted", False)),
            hidden=bool(data.get("hidden", False)),
            locked=bool(data.get("locked", False)),
            solo=bool(data.get("solo", False)),
            scene_role=data.get("scene_role"),
        )


@dataclass
class Project:
    name: str = "Untitled Project"
    tracks: list[Track] = field(default_factory=list)
    media_library: list[MediaAsset] = field(default_factory=list)
    px_per_sec: float = 70.0
    duration: float = 0.0
    markers: list[TimelineMarker] = field(default_factory=list)
    in_point: float | None = None
    out_point: float | None = None
    bpm: float = 120.0
    snap_settings: SnapSettings = field(default_factory=SnapSettings)
    ripple_edit: bool = False
    canvas_width: int = 1280
    canvas_height: int = 720
    aspect_ratio_id: str = "16:9"
    playlist: PlaylistSettings = field(default_factory=PlaylistSettings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tracks": [t.to_dict() for t in self.tracks],
            "media_library": [m.to_dict() for m in self.media_library],
            "px_per_sec": self.px_per_sec,
            "duration": self.duration,
            "markers": [m.to_dict() for m in self.markers],
            "in_point": self.in_point,
            "out_point": self.out_point,
            "bpm": self.bpm,
            "snap_settings": self.snap_settings.to_dict(),
            "ripple_edit": self.ripple_edit,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "aspect_ratio_id": self.aspect_ratio_id,
            "playlist": self.playlist.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            name=data.get("name", "Untitled Project"),
            tracks=[Track.from_dict(t) for t in data.get("tracks", [])],
            media_library=[MediaAsset.from_dict(m) for m in data.get("media_library", [])],
            px_per_sec=float(data.get("px_per_sec", 70.0)),
            duration=float(data.get("duration", 0.0)),
            markers=[TimelineMarker.from_dict(m) for m in data.get("markers", [])],
            in_point=data.get("in_point"),
            out_point=data.get("out_point"),
            bpm=float(data.get("bpm", 120.0)),
            snap_settings=SnapSettings.from_dict(data.get("snap_settings", {})),
            ripple_edit=bool(data.get("ripple_edit", False)),
            canvas_width=int(data.get("canvas_width", 1280)),
            canvas_height=int(data.get("canvas_height", 720)),
            aspect_ratio_id=str(data.get("aspect_ratio_id", "16:9")),
            playlist=PlaylistSettings.from_dict(data.get("playlist", {})),
        )
