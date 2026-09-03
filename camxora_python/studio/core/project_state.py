"""Mutable editing state: the current Project plus selection/playhead/undo-redo.

This is the Python analog of the reference app's global `state` object plus
its mutation functions (addTrack, handleDrop, startDragMove/startTrim,
splitAtPlayhead, duplicateClip, deleteClip, activeClipsAt, computeOpacity).

Gesture-based edits (drag-move, drag-trim) are committed to the model ONCE
per completed gesture (on mouse release), not on every mouse-move — the UI
layer does its own live-preview math (using the same `snap`/`clamp` helpers)
for visual feedback during the drag, then calls `move_clip`/`trim_clip` once
with the final values. This avoids compounding-mutation bugs and keeps each
gesture as exactly one undo step.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any, Literal

from studio.core.models import Clip, MediaAsset, Project, Track, new_id
from studio.core.time_utils import clamp, snap

_MAX_UNDO = 100
_MIN_CLIP_DURATION = 0.2


def normalize_media_path(path: str) -> str:
    """Stable path key for duplicate detection (Windows-safe)."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


TEXT_PRESETS: dict[str, dict[str, Any]] = {
    "title": {"text": "Your Title Here", "size": 52, "color": "#ffffff", "y": 0.46},
    "subtitle": {"text": "Subtitle text", "size": 30, "color": "#ffdca8", "y": 0.58},
    "caption": {"text": "Lower third caption", "size": 22, "color": "#ffffff", "y": 0.86},
}


@dataclass
class ActiveClips:
    video: list[tuple[Track, Clip]] = field(default_factory=list)
    audio: list[tuple[Track, Clip]] = field(default_factory=list)
    overlay: list[tuple[Track, Clip]] = field(default_factory=list)


class ProjectState:
    def __init__(self, project: Project | None = None) -> None:
        self.project: Project = project or Project()
        self.selected_clip_id: str | None = None
        self.selected_clip_ids: set[str] = set()
        self.playhead: float = 0.0
        self.is_playing: bool = False
        self.playlist_preview_active: bool = False
        self.playlist_overlay_enabled: bool = False

        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []

    # ---------------- undo / redo ----------------

    def _push_undo(self) -> None:
        self._undo_stack.append(copy.deepcopy(self.project.to_dict()))
        if len(self._undo_stack) > _MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append(copy.deepcopy(self.project.to_dict()))
        data = self._undo_stack.pop()
        self.project = Project.from_dict(data)
        self._sanitize_selection()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append(copy.deepcopy(self.project.to_dict()))
        data = self._redo_stack.pop()
        self.project = Project.from_dict(data)
        self._sanitize_selection()
        return True

    def _sanitize_selection(self) -> None:
        self.selected_clip_ids = {
            cid for cid in self.selected_clip_ids if self.get_clip(cid) is not None
        }
        if self.selected_clip_id and self.get_clip(self.selected_clip_id) is None:
            self.selected_clip_id = next(iter(self.selected_clip_ids), None)
        elif self.selected_clip_id and self.selected_clip_id not in self.selected_clip_ids:
            if self.selected_clip_ids:
                self.selected_clip_id = next(iter(self.selected_clip_ids))
            else:
                self.selected_clip_id = None
        elif not self.selected_clip_ids and self.selected_clip_id:
            if self.get_clip(self.selected_clip_id):
                self.selected_clip_ids = {self.selected_clip_id}
            else:
                self.selected_clip_id = None

    def _effective_selection(self) -> list[str]:
        if self.selected_clip_ids:
            return list(self.selected_clip_ids)
        if self.selected_clip_id:
            return [self.selected_clip_id]
        return []

    def select_clip(self, clip_id: str, *, additive: bool = False, toggle: bool = False) -> None:
        if self.get_clip(clip_id) is None:
            return
        if toggle:
            if clip_id in self.selected_clip_ids:
                self.selected_clip_ids.discard(clip_id)
                if self.selected_clip_id == clip_id:
                    self.selected_clip_id = next(iter(self.selected_clip_ids), None)
            else:
                self.selected_clip_ids.add(clip_id)
                self.selected_clip_id = clip_id
        elif additive:
            self.selected_clip_ids.add(clip_id)
            self.selected_clip_id = clip_id
        else:
            self.selected_clip_ids = {clip_id}
            self.selected_clip_id = clip_id

    def select_clips(self, clip_ids: set[str]) -> None:
        valid = {cid for cid in clip_ids if self.get_clip(cid) is not None}
        self.selected_clip_ids = valid
        self.selected_clip_id = next(iter(valid), None)

    def clear_selection(self) -> None:
        self.selected_clip_ids.clear()
        self.selected_clip_id = None

    def toggle_ripple_edit(self) -> bool:
        self.project.ripple_edit = not self.project.ripple_edit
        return self.project.ripple_edit

    def replace_project(self, project: Project) -> None:
        """Swap in a wholly new `Project` (e.g. after loading a file) and
        reset selection/playhead/undo history — the loaded project starts
        with a clean slate rather than inheriting the previous project's
        edit history."""
        self.project = project
        self.selected_clip_id = None
        self.selected_clip_ids.clear()
        self.playhead = 0.0
        self.is_playing = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ---------------- tracks ----------------

    def default_track_name(self, track_type: str) -> str:
        count = sum(1 for t in self.project.tracks if t.type == track_type) + 1
        return str(count)

    def _create_track(self, track_type: Literal["video", "audio", "overlay"], name: str | None = None) -> Track:
        track = Track(id=new_id("trk"), type=track_type, name=name or self.default_track_name(track_type))
        self.project.tracks.append(track)
        return track

    def add_track(self, track_type: Literal["video", "audio", "overlay"], name: str | None = None) -> Track:
        self._push_undo()
        return self._create_track(track_type, name)

    @staticmethod
    def required_track_type_for_clip(clip: Clip) -> str:
        if clip.kind == "text" or clip.kind == "playlist":
            return "overlay"
        if clip.kind in ("video", "audio", "image"):
            return ProjectState._required_track_type_for_media(clip.kind)
        return "overlay"

    def reorder_track(self, track_id: str, new_index: int) -> None:
        tracks = self.project.tracks
        old_index = next((i for i, t in enumerate(tracks) if t.id == track_id), None)
        if old_index is None:
            return
        new_index = max(0, min(new_index, len(tracks) - 1))
        if old_index == new_index:
            return
        self._push_undo()
        track = tracks.pop(old_index)
        tracks.insert(new_index, track)

    def remove_track(self, track_id: str) -> None:
        track = self.get_track(track_id)
        if track is None or track.locked or track.scene_role:
            return
        self._push_undo()
        for clip in track.clips:
            self.selected_clip_ids.discard(clip.id)
            if self.selected_clip_id == clip.id:
                self.selected_clip_id = None
        self.project.tracks = [t for t in self.project.tracks if t.id != track_id]
        self._sanitize_selection()
        self.recalc_duration()

    def prune_empty_tracks(self) -> None:
        """Remove extra empty tracks (e.g. leftover Overlay 2 after a clip move).

        Keeps a single empty track per type so users still have a drop target.
        """
        if not self.project.tracks:
            return
        type_totals: dict[str, int] = {}
        for track in self.project.tracks:
            type_totals[track.type] = type_totals.get(track.type, 0) + 1
        kept: list[Track] = []
        removed = False
        for track in self.project.tracks:
            if track.clips:
                kept.append(track)
                continue
            if type_totals.get(track.type, 0) <= 1:
                kept.append(track)
                continue
            type_totals[track.type] -= 1
            removed = True
        if removed:
            self.project.tracks = kept
            self._sanitize_selection()
            self.recalc_duration()

    def toggle_track_mute(self, track_id: str) -> None:
        self._push_undo()
        for t in self.project.tracks:
            if t.id == track_id:
                t.muted = not t.muted

    def toggle_track_hidden(self, track_id: str) -> None:
        self._push_undo()
        for t in self.project.tracks:
            if t.id == track_id:
                t.hidden = not t.hidden

    def toggle_track_lock(self, track_id: str) -> None:
        self._push_undo()
        for t in self.project.tracks:
            if t.id == track_id:
                t.locked = not t.locked

    def toggle_track_solo(self, track_id: str) -> None:
        self._push_undo()
        target = self.get_track(track_id)
        if target is None:
            return
        new_solo = not target.solo
        if new_solo:
            for t in self.project.tracks:
                t.solo = t.id == track_id
        else:
            target.solo = False

    def rename_track(self, track_id: str, name: str) -> None:
        track = self.get_track(track_id)
        if track is None:
            return
        cleaned = name.strip()
        if not cleaned or cleaned == track.name:
            return
        self._push_undo()
        track.name = cleaned

    def get_track(self, track_id: str) -> Track | None:
        return next((t for t in self.project.tracks if t.id == track_id), None)

    # ---------------- clip lookup ----------------

    def get_clip(self, clip_id: str | None) -> tuple[Track, Clip] | None:
        if not clip_id:
            return None
        for track in self.project.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return track, clip
        return None

    # ---------------- clip creation (drag from library) ----------------

    def resolve_overlap(self, track: Track, clip: Clip) -> None:
        """Push `clip` forward until it no longer overlaps siblings on `track`."""
        if self.project.ripple_edit:
            return
        moved = True
        guard = 0
        while moved and guard < 50:
            moved = False
            guard += 1
            for other in track.clips:
                if other.id == clip.id:
                    continue
                a_start, a_end = clip.start, clip.end
                b_start, b_end = other.start, other.end
                if a_start < b_end and b_start < a_end:
                    clip.start = b_end
                    moved = True

    @staticmethod
    def _required_track_type_for_media(media_type: str) -> str:
        return {"video": "video", "audio": "audio", "image": "overlay"}[media_type]

    def _insert_clip_from_media(self, media: MediaAsset, track: Track, drop_time: float) -> Clip:
        if not track.clips:
            drop_time = 0.0
        duration = 5.0 if media.type == "image" else (media.duration or 5.0)
        clip = Clip(
            id=new_id("clip"),
            track_id=track.id,
            media_id=media.id,
            kind=media.type,
            label=media.name,
            start=snap(max(0.0, drop_time)),
            duration=duration,
            filter="none",
            opacity=1.0,
            volume=1.0,
            viz="bars",
            viz_enabled=False,
            thumb=media.path if media.type == "image" else None,
        )
        self.resolve_overlap(track, clip)
        track.clips.append(clip)
        self._autolink_companion_clips(clip, media)
        self.select_clip(clip.id)
        self.recalc_duration()
        return clip

    def _autolink_companion_clips(self, clip: Clip, media: MediaAsset) -> None:
        """S15 — link video/audio clips that share the same media at the same time."""
        if media.type not in ("video", "audio") or not clip.media_id:
            return
        for track in self.project.tracks:
            for other in track.clips:
                if other.id == clip.id or other.media_id != clip.media_id:
                    continue
                if abs(other.start - clip.start) > 0.2:
                    continue
                group = clip.linked_group_id or other.linked_group_id or new_id("link")
                clip.linked_group_id = group
                other.linked_group_id = group

    def add_clip_from_media(self, media: MediaAsset, track: Track, drop_time: float) -> Clip | None:
        if track.type != self._required_track_type_for_media(media.type):
            return None
        self._push_undo()
        return self._insert_clip_from_media(media, track, drop_time)

    def add_clip_from_media_at_row(self, media: MediaAsset, row_index: int, drop_time: float) -> Clip:
        """Timeline-drop entry point: places `media` on the track at
        `row_index` (the row under the cursor) if it's already the right
        type for `media`, otherwise creates a new matching-type track first
        — CapCut-style "drop anywhere" behavior, since a real editor never
        makes you manually add a track before dragging media onto the
        timeline. Track creation + clip insertion is a single undo step,
        matching the one drag gesture that caused both.
        """
        required_type = self._required_track_type_for_media(media.type)
        self._push_undo()
        tracks = self.project.tracks
        track = tracks[row_index] if 0 <= row_index < len(tracks) else None
        if track is None or track.type != required_type:
            track = self._create_track(required_type)
        return self._insert_clip_from_media(media, track, drop_time)

    def _insert_text_clip(self, track: Track, preset: str, drop_time: float) -> Clip:
        if not track.clips:
            drop_time = 0.0
        p = TEXT_PRESETS[preset]
        clip = Clip(
            id=new_id("clip"),
            track_id=track.id,
            kind="text",
            label=str(p["text"]),
            start=snap(max(0.0, drop_time)),
            duration=4.0,
            text=str(p["text"]),
            color=str(p["color"]),
            size=float(p["size"]),
            x=0.5,
            y=float(p["y"]),
            opacity=1.0,
            fade_in=0.3,
            fade_out=0.3,
        )
        self.resolve_overlap(track, clip)
        track.clips.append(clip)
        self.select_clip(clip.id)
        self.recalc_duration()
        return clip

    def add_text_clip(self, track: Track, preset: str, drop_time: float) -> Clip | None:
        if track.type != "overlay" or preset not in TEXT_PRESETS:
            return None
        self._push_undo()
        return self._insert_text_clip(track, preset, drop_time)

    def add_text_clip_at_row(self, preset: str, row_index: int, drop_time: float) -> Clip | None:
        """Timeline-drop entry point for text presets — same "drop
        anywhere, auto-create the track" behavior as
        `add_clip_from_media_at_row`, since text can only live on an
        overlay track."""
        if preset not in TEXT_PRESETS:
            return None
        self._push_undo()
        tracks = self.project.tracks
        track = tracks[row_index] if 0 <= row_index < len(tracks) else None
        if track is None or track.type != "overlay":
            track = self._create_track("overlay")
        return self._insert_text_clip(track, preset, drop_time)

    # ---------------- clip move / trim (one commit per gesture) ----------------

    @staticmethod
    def _ripple_close_gap(track: Track, gap_start: float, gap_duration: float, exclude_id: str | None = None) -> None:
        gap_end = gap_start + gap_duration
        for clip in track.clips:
            if exclude_id is not None and clip.id == exclude_id:
                continue
            if clip.start >= gap_end - 1e-9:
                clip.start = max(0.0, snap(clip.start - gap_duration))

    @staticmethod
    def _ripple_open_gap(
        track: Track,
        insert_at: float,
        gap_duration: float,
        exclude_ids: set[str] | None = None,
    ) -> None:
        skip = exclude_ids or set()
        for clip in sorted(track.clips, key=lambda c: -c.start):
            if clip.id in skip:
                continue
            if clip.start >= insert_at - 1e-9:
                clip.start = snap(clip.start + gap_duration)

    def _ripple_move_on_track(self, track: Track, clip: Clip, new_start: float) -> None:
        old_start = clip.start
        delta = new_start - old_start
        if abs(delta) < 1e-9:
            return
        old_end = old_start + clip.duration
        clip.start = new_start
        for other in track.clips:
            if other.id == clip.id:
                continue
            if other.start >= old_end - 1e-9:
                other.start = max(0.0, snap(other.start + delta))

    def _ripple_shift_after(self, track: Track, pivot_time: float, delta: float, exclude_id: str | None = None) -> None:
        if abs(delta) < 1e-9:
            return
        for clip in track.clips:
            if exclude_id is not None and clip.id == exclude_id:
                continue
            if clip.start >= pivot_time - 1e-9:
                clip.start = max(0.0, snap(clip.start + delta))

    def move_clips_by_delta(self, clip_ids: list[str], delta: float) -> None:
        if abs(delta) < 1e-9:
            return
        refs = [self.get_clip(cid) for cid in clip_ids]
        pairs = [r for r in refs if r is not None]
        if not pairs:
            return
        self._push_undo()
        for track, clip in pairs:
            if track.locked:
                continue
            target_start = max(0.0, snap(clip.start + delta))
            if self.project.ripple_edit:
                self._ripple_move_on_track(track, clip, target_start)
            else:
                clip.start = target_start
        self.recalc_duration()

    def linked_clip_ids(self, clip_id: str) -> list[str]:
        ref = self.get_clip(clip_id)
        if ref is None:
            return []
        _track, clip = ref
        if not clip.linked_group_id:
            return [clip_id]
        ids: list[str] = []
        for track in self.project.tracks:
            for other in track.clips:
                if other.linked_group_id == clip.linked_group_id:
                    ids.append(other.id)
        return ids or [clip_id]

    def move_clip(self, clip_id: str, new_start_raw: float) -> None:
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        track, clip = ref
        if track.locked:
            return
        new_start = max(0.0, snap(new_start_raw))
        delta = new_start - clip.start
        if abs(delta) < 1e-9:
            return
        self._push_undo()
        move_ids = self.linked_clip_ids(clip_id)
        if len(self.selected_clip_ids) > 1 and clip_id in self.selected_clip_ids:
            move_ids = list(dict.fromkeys(list(self.selected_clip_ids) + move_ids))
        for lid in move_ids:
            lref = self.get_clip(lid)
            if lref is None:
                continue
            ltrack, lclip = lref
            if ltrack.locked:
                continue
            target_start = max(0.0, snap(lclip.start + delta))
            if self.project.ripple_edit:
                self._ripple_move_on_track(ltrack, lclip, target_start)
            else:
                lclip.start = target_start
                self.resolve_overlap(ltrack, lclip)
        self.recalc_duration()

    def trim_clip(self, clip_id: str, side: Literal["left", "right"], dt: float) -> None:
        """Apply a trim gesture. `dt` is the total mouse-delta (seconds) from
        drag start, measured against the clip's pre-drag geometry.

        Trims are clamped against the adjacent clip on the same track rather
        than using `resolve_overlap`'s "push forward" semantics — those are
        meant for placing/moving a *whole* clip, not for extending/shrinking
        one edge, and pushing the clip forward on a right-trim would corrupt
        its position instead of simply capping how far it can extend. This
        way a trim can never create an overlapping pair of clips.

        A no-op trim (the resolved change ends up identical to the clip's
        current geometry — e.g. a plain click inside the edge-handle zone
        with no actual drag) does not push an undo step.
        """
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        track, clip = ref
        orig_start, orig_duration, orig_trim_start = clip.start, clip.duration, clip.trim_start
        orig_end = orig_start + orig_duration

        if side == "right":
            raw_duration = max(_MIN_CLIP_DURATION, snap(orig_duration + dt))
            if not self.project.ripple_edit:
                next_start = min(
                    (c.start for c in track.clips if c.id != clip.id and c.start >= orig_end),
                    default=None,
                )
                if next_start is not None:
                    raw_duration = min(raw_duration, max(_MIN_CLIP_DURATION, next_start - orig_start))
            new_duration = raw_duration
            media_max = self.clip_media_max_duration(clip, orig_trim_start)
            if media_max is not None:
                new_duration = min(new_duration, media_max)
            if new_duration == orig_duration:
                return
            self._push_undo()
            clip.duration = new_duration
            if self.project.ripple_edit:
                self._ripple_shift_after(track, orig_end, new_duration - orig_duration, exclude_id=clip.id)
        else:
            prev_end = max(
                (c.end for c in track.clips if c.id != clip.id and c.end <= orig_start),
                default=0.0,
            )
            if clip.kind in ("image", "text"):
                new_start = max(prev_end, 0.0, snap(orig_start + dt))
                delta = new_start - orig_start
                if delta == 0.0 or orig_duration - delta <= _MIN_CLIP_DURATION:
                    return
                self._push_undo()
                clip.start = new_start
                clip.duration = orig_duration - delta
            else:
                min_start = self.clip_media_min_start(orig_start, orig_trim_start, clip_kind=clip.kind)
                new_start = max(prev_end, min_start, snap(orig_start + dt))
                delta = new_start - orig_start
                if delta == 0.0 or orig_duration - delta <= _MIN_CLIP_DURATION:
                    return
                self._push_undo()
                clip.start = new_start
                clip.duration = orig_duration - delta
                clip.trim_start = orig_trim_start + delta

        self.recalc_duration()

    @staticmethod
    def _clip_compatible_with_track(clip: Clip, track: Track) -> bool:
        if track.locked:
            return False
        if clip.kind == "text":
            return track.type == "overlay"
        if clip.kind in ("video", "audio", "image"):
            return track.type == ProjectState._required_track_type_for_media(clip.kind)
        return track.type == "overlay"

    def move_clip_to_track(self, clip_id: str, target_track_id: str, new_start_raw: float) -> None:
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        source_track, clip = ref
        target = self.get_track(target_track_id)
        if target is None or source_track.locked:
            return
        if not self._clip_compatible_with_track(clip, target):
            return
        new_start = max(0.0, snap(new_start_raw))
        if target.id == source_track.id:
            self.move_clip(clip_id, new_start)
            return
        self._push_undo()
        source_track.clips = [c for c in source_track.clips if c.id != clip_id]
        clip.track_id = target.id
        clip.start = new_start
        target.clips.append(clip)
        self.resolve_overlap(target, clip)
        self.recalc_duration()

    def move_clip_to_new_track_at_row(self, clip_id: str, row_index: int, new_start_raw: float) -> None:
        """Split one clip onto its own new track at ``row_index`` (CapCut-style row split)."""
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        source_track, clip = ref
        if source_track.locked:
            return
        required = self.required_track_type_for_clip(clip)
        new_start = max(0.0, snap(new_start_raw))
        self._push_undo()
        new_track = self._create_track(required)
        source_track.clips = [c for c in source_track.clips if c.id != clip_id]
        clip.track_id = new_track.id
        clip.start = new_start
        new_track.clips.append(clip)
        self.resolve_overlap(new_track, clip)
        clamped = max(0, min(row_index, len(self.project.tracks) - 1))
        if clamped != len(self.project.tracks) - 1:
            track = self.project.tracks.pop()
            self.project.tracks.insert(clamped, track)
        self.recalc_duration()

    def clip_media_max_duration(self, clip: Clip, trim_start: float | None = None) -> float | None:
        """Max timeline duration for audio/video clips based on source media length."""
        if clip.kind in ("image", "text"):
            return None
        if not clip.media_id:
            return None
        media = self.get_media(clip.media_id)
        if media is None or media.type not in ("video", "audio"):
            return None
        source_len = media.duration or 0.0
        if source_len <= 0:
            return None
        ts = clip.trim_start if trim_start is None else trim_start
        return max(_MIN_CLIP_DURATION, source_len - ts)

    @staticmethod
    def clip_media_min_start(orig_start: float, orig_trim_start: float, *, clip_kind: str = "video") -> float:
        """Earliest timeline start when trimming left.

        Image/text overlays are still images — extending left only moves the clip
        on the timeline (no source media trim window). Video/audio are bounded by
        ``trim_start >= 0``.
        """
        if clip_kind in ("image", "text"):
            return 0.0
        return max(0.0, orig_start - orig_trim_start)

    def split_clip_at_playhead(self, clip_id: str | None = None) -> Clip | None:
        clip_id = clip_id or self.selected_clip_id
        ref = self.get_clip(clip_id)
        if ref is None:
            return None
        track, clip = ref
        t = self.playhead
        if t <= clip.start or t >= clip.end:
            return None
        self._push_undo()
        right_duration = clip.end - t
        copy_clip = copy.deepcopy(clip)
        copy_clip.id = new_id("clip")
        copy_clip.start = t
        copy_clip.duration = right_duration
        copy_clip.trim_start = clip.trim_start + (t - clip.start)
        clip.duration = t - clip.start
        track.clips.append(copy_clip)
        self.recalc_duration()
        return copy_clip

    def duplicate_clip(self, clip_id: str | None = None) -> Clip | None:
        copies = self.duplicate_selected_clips() if clip_id is None else None
        if copies is not None:
            return copies[0] if copies else None
        ref = self.get_clip(clip_id)
        if ref is None:
            return None
        track, clip = ref
        self._push_undo()
        copy_clip = copy.deepcopy(clip)
        copy_clip.id = new_id("clip")
        copy_clip.start = clip.end
        copy_clip.linked_group_id = None
        self.resolve_overlap(track, copy_clip)
        track.clips.append(copy_clip)
        self.select_clip(copy_clip.id)
        self.recalc_duration()
        return copy_clip

    def duplicate_selected_clips(self) -> list[Clip]:
        ids = self._effective_selection()
        if not ids:
            return []
        self._push_undo()
        copies: list[Clip] = []
        for clip_id in ids:
            ref = self.get_clip(clip_id)
            if ref is None:
                continue
            track, clip = ref
            if track.locked:
                continue
            copy_clip = copy.deepcopy(clip)
            copy_clip.id = new_id("clip")
            copy_clip.start = clip.end
            copy_clip.linked_group_id = None
            self.resolve_overlap(track, copy_clip)
            track.clips.append(copy_clip)
            copies.append(copy_clip)
        if copies:
            self.select_clips({c.id for c in copies})
        self.recalc_duration()
        return copies

    def delete_clip(self, clip_id: str | None = None) -> bool:
        return self.delete_selected_clips(single_id=clip_id) > 0

    def delete_selected_clips(self, *, single_id: str | None = None) -> int:
        ids = [single_id] if single_id else self._effective_selection()
        if not ids:
            return 0
        refs: list[tuple[Track, Clip]] = []
        for cid in ids:
            ref = self.get_clip(cid)
            if ref is not None:
                refs.append(ref)
        if not refs:
            return 0
        self._push_undo()
        refs.sort(key=lambda pair: pair[1].start, reverse=True)
        removed = 0
        for track, clip in refs:
            if track.locked:
                continue
            if self.project.ripple_edit:
                self._ripple_close_gap(track, clip.start, clip.duration)
            track.clips = [c for c in track.clips if c.id != clip.id]
            self.selected_clip_ids.discard(clip.id)
            if self.selected_clip_id == clip.id:
                self.selected_clip_id = None
            removed += 1
        if self.selected_clip_id is None and self.selected_clip_ids:
            self.selected_clip_id = next(iter(self.selected_clip_ids))
        self.recalc_duration()
        return removed

    def nudge_selected_clips(
        self,
        delta: float,
        *,
        snap_to_edge: bool = False,
        edge_direction: int = 0,
    ) -> None:
        ids = self._effective_selection()
        if not ids:
            return
        if snap_to_edge and edge_direction != 0:
            for clip_id in ids:
                self.snap_clip_to_edge(clip_id, edge_direction)
            return
        self.move_clips_by_delta(ids, delta)

    def snap_clip_to_edge(self, clip_id: str, direction: int) -> None:
        """Alt+nudge: snap clip start (direction < 0) or end (direction > 0) to nearest neighbor edge."""
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        track, clip = ref
        if track.locked:
            return
        others = [c for c in track.clips if c.id != clip.id]
        if direction < 0:
            targets = [0.0, self.playhead] + [c.start for c in others] + [c.end for c in others]
            candidates = [t for t in targets if t <= clip.start + 1e-6]
            if not candidates:
                return
            new_start = max(candidates)
            if abs(new_start - clip.start) < 1e-9:
                return
            self.move_clip(clip_id, new_start)
        else:
            targets = [c.start for c in others] + [c.end for c in others] + [self.project.duration]
            candidates = [t for t in targets if t >= clip.end - 1e-6]
            if not candidates:
                return
            new_end = min(candidates)
            new_start = new_end - clip.duration
            if new_start < 0:
                return
            if abs(new_start - clip.start) < 1e-9:
                return
            self.move_clip(clip_id, new_start)

    def detach_linked_audio(self, video_clip_id: str) -> bool:
        ref = self.get_clip(video_clip_id)
        if ref is None:
            return False
        _track, clip = ref
        if clip.kind != "video" or not clip.linked_group_id:
            return False
        audio_pair: tuple[Track, Clip] | None = None
        for track in self.project.tracks:
            for other in track.clips:
                if other.linked_group_id == clip.linked_group_id and other.kind == "audio":
                    audio_pair = (track, other)
                    break
            if audio_pair is not None:
                break
        if audio_pair is None:
            return False
        self._push_undo()
        clip.linked_group_id = None
        audio_pair[1].linked_group_id = None
        return True

    def update_clip(self, clip_id: str, *, record_undo: bool = True, **fields: Any) -> None:
        """Generic property setter for Inspector-bound fields (color, size,
        x, y, volume, opacity, fade_in, fade_out, filter, viz, viz_enabled,
        text, transform_*, crop_inset). Pushes one undo step per call unless
        ``record_undo=False`` (used for live slider preview)."""
        ref = self.get_clip(clip_id)
        if ref is None:
            return
        _track, clip = ref
        if record_undo:
            self._push_undo()
        for key, value in fields.items():
            if hasattr(clip, key):
                setattr(clip, key, value)
                if key == "text" and value:
                    clip.label = str(value)[:24]

    # ---------------- derived state ----------------

    def recalc_duration(self) -> float:
        max_end = 0.0
        for track in self.project.tracks:
            for clip in track.clips:
                max_end = max(max_end, clip.end)
        self.project.duration = max_end
        return max_end

    def canvas_size(self) -> tuple[int, int]:
        from core.preview_settings import canvas_size_for_project

        return canvas_size_for_project(self.project)

    def set_aspect_ratio(self, preset_id: str) -> tuple[int, int]:
        from core.preview_settings import apply_aspect_ratio

        return apply_aspect_ratio(self.project, preset_id)

    def has_timeline_clips(self) -> bool:
        """True when at least one clip exists on any track."""
        return any(track.clips for track in self.project.tracks)

    def active_clips_at(self, time: float) -> ActiveClips:
        result = ActiveClips()
        for track in self.project.tracks:
            if track.hidden and track.type != "audio":
                continue
            bucket = getattr(result, track.type)
            for clip in track.clips:
                if clip.start <= time < clip.end:
                    bucket.append((track, clip))
        return result

    @staticmethod
    def compute_opacity(clip: Clip, time: float) -> float:
        op = clip.opacity if clip.opacity is not None else 1.0
        rel = time - clip.start
        remain = clip.end - time
        if clip.fade_in and rel < clip.fade_in:
            op *= clamp(rel / clip.fade_in, 0.0, 1.0)
        if clip.fade_out and remain < clip.fade_out:
            op *= clamp(remain / clip.fade_out, 0.0, 1.0)
        return op

    def seek(self, time: float) -> None:
        self.playhead = clamp(time, 0.0, max(self.project.duration, 0.0))

    def add_media(self, media: MediaAsset) -> None:
        self.project.media_library.append(media)

    def get_media(self, media_id: str | None) -> MediaAsset | None:
        if not media_id:
            return None
        return next((m for m in self.project.media_library if m.id == media_id), None)

    def find_media_by_path(self, path: str | None) -> MediaAsset | None:
        """Return library media for a file path (case-insensitive, normalized)."""
        if not path:
            return None
        target = normalize_media_path(path)
        for media in self.project.media_library:
            if normalize_media_path(media.path) == target:
                return media
        return None

    def update_media(self, media_id: str, **fields: Any) -> None:
        media = self.get_media(media_id)
        if media is None:
            return
        for key, value in fields.items():
            if hasattr(media, key):
                setattr(media, key, value)

    def update_playlist_component(
        self,
        component_id: str,
        *,
        record_undo: bool = False,
        **fields: float,
    ) -> None:
        if record_undo:
            self._push_undo()
        layout = self.project.playlist.component_layout.setdefault(component_id, {})
        for key, value in fields.items():
            if key in ("x", "y", "w", "h"):
                layout[key] = float(value)

    def set_playlist_selected_component(self, component_id: str | None) -> None:
        self.project.playlist.selected_component = component_id

    def _find_playlist_audio_track(self) -> Track | None:
        from core.playlist_scene_sync import SCENE_AUDIO

        for track in self.project.tracks:
            if track.scene_role == SCENE_AUDIO:
                return track
            if track.type == "audio" and track.name == "Playlist":
                return track
        return None

    def has_playlist_content(self) -> bool:
        if self.project.playlist.song_ids:
            return True
        track = self._find_playlist_audio_track()
        return track is not None and bool(track.clips)

    def sync_playlist_to_timeline(self, *, record_undo: bool = True) -> None:
        """Place playlist songs sequentially on the dedicated Playlist audio track."""
        from core.playlist_scene_sync import SCENE_AUDIO, sync_playlist_scene_to_timeline

        song_ids = list(self.project.playlist.song_ids)
        if record_undo:
            self._push_undo()

        track = self._find_playlist_audio_track()
        if not song_ids:
            if track is not None:
                track.clips.clear()
            sync_playlist_scene_to_timeline(self, record_undo=False)
            self.recalc_duration()
            return

        if track is None:
            track = self._create_track("audio", name="Playlist")
        track.scene_role = SCENE_AUDIO
        track.locked = True
        track.name = "Playlist"

        track.clips.clear()
        start = 0.0
        for media_id in song_ids:
            media = self.get_media(media_id)
            if media is None or media.type != "audio":
                continue
            duration = float(media.duration or 5.0)
            clip = Clip(
                id=new_id("clip"),
                track_id=track.id,
                media_id=media.id,
                kind="audio",
                label=media.name,
                start=start,
                duration=duration,
                filter="none",
                opacity=1.0,
                volume=1.0,
                viz="bars",
                viz_enabled=False,
            )
            track.clips.append(clip)
            start += duration

        sync_playlist_scene_to_timeline(self, record_undo=False)
        self.recalc_duration()
