"""Professional magnetic snap — S1–S18 target collection, priority, and resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from studio.core.models import Clip
from studio.core.project_state import ProjectState
from studio.core.snap_models import SnapSettings
from studio.core.time_utils import clamp, snap

DEFAULT_SNAP_THRESHOLD_PX = 10.0

SnapEdge = Literal["start", "end", "center", "none"]

# Lower priority value = wins when distances tie (S6).
_PRIORITY = {
    "clip_edge_same_track": 0,
    "clip_center_same_track": 1,
    "playhead": 2,
    "marker": 3,
    "in_out": 3,
    "clip_edge_same_type": 4,
    "clip_center_same_type": 5,
    "clip_edge_other": 6,
    "clip_center_other": 7,
    "beat": 8,
    "frame": 9,
    "sequence_end": 10,
    "zero": 11,
}


@dataclass
class SnapTarget:
    time: float
    kind: str
    priority: int
    track_id: str | None = None
    track_type: str | None = None


@dataclass
class SnapResult:
    time: float
    snapped: bool = False
    active_guide: float | None = None
    nearby_guides: list[float] = field(default_factory=list)
    edge: SnapEdge = "none"

    @property
    def guides(self) -> list[float]:
        """Backward-compatible guide list (active first)."""
        if self.active_guide is None:
            return self.nearby_guides
        if self.active_guide in self.nearby_guides:
            return self.nearby_guides
        return [self.active_guide, *self.nearby_guides]


@dataclass
class SnapContext:
    project_state: ProjectState
    px_per_sec: float
    exclude_clip_id: str | None = None
    track_id: str | None = None
    track_type: str | None = None
    temporary_disabled: bool = False
    clip_duration: float | None = None


def effective_threshold_sec(settings: SnapSettings, px_per_sec: float) -> float:
    """S3 — zoom-aware threshold clamped to a sensible seconds window."""
    if px_per_sec <= 0:
        return 0.5
    sec = settings.threshold_px / px_per_sec
    return clamp(sec, 0.015, 0.45)


def is_snap_active(ctx: SnapContext) -> bool:
    """S1 + S2 — global toggle and temporary Alt override."""
    if ctx.temporary_disabled:
        return False
    return ctx.project_state.project.snap_settings.enabled


def _track_matches_scope(scope: str, track_type: str, ctx: SnapContext) -> bool:
    if scope == "all":
        return True
    if scope == "same_track":
        return ctx.track_id is not None and ctx.track_type == track_type
    return scope == track_type


def _clip_edge_priority(track_id: str, track_type: str, ctx: SnapContext) -> int:
    if ctx.track_id and track_id == ctx.track_id:
        return _PRIORITY["clip_edge_same_track"]
    if ctx.track_type and track_type == ctx.track_type:
        return _PRIORITY["clip_edge_same_type"]
    return _PRIORITY["clip_edge_other"]


def _clip_center_priority(track_id: str, track_type: str, ctx: SnapContext) -> int:
    if ctx.track_id and track_id == ctx.track_id:
        return _PRIORITY["clip_center_same_track"]
    if ctx.track_type and track_type == ctx.track_type:
        return _PRIORITY["clip_center_same_type"]
    return _PRIORITY["clip_center_other"]


def _frame_targets_near(raw_time: float, settings: SnapSettings, px_per_sec: float) -> list[SnapTarget]:
    """S4 — frame grid when zoomed in enough to see individual frames."""
    if not settings.snap_to_frames or settings.frame_rate <= 0:
        return []
    frame_sec = 1.0 / settings.frame_rate
    if px_per_sec * frame_sec < 3.0:
        return []
    frame_index = round(raw_time / frame_sec)
    times = [(frame_index + offset) * frame_sec for offset in (-1, 0, 1)]
    return [SnapTarget(t, "frame", _PRIORITY["frame"]) for t in times if t >= 0]


def _beat_targets(project_duration: float, bpm: float) -> list[SnapTarget]:
    """S14 — musical beat grid."""
    if bpm <= 0 or project_duration <= 0:
        return []
    beat_sec = 60.0 / bpm
    targets: list[SnapTarget] = []
    t = 0.0
    while t <= project_duration + beat_sec:
        targets.append(SnapTarget(t, "beat", _PRIORITY["beat"]))
        t += beat_sec
    return targets


def collect_snap_targets(ctx: SnapContext) -> list[SnapTarget]:
    """Collect all snap targets respecting scope (S11) and locked tracks (S12)."""
    state = ctx.project_state
    project = state.project
    settings = project.snap_settings
    scope = settings.scope
    targets: list[SnapTarget] = []

    targets.append(SnapTarget(0.0, "zero", _PRIORITY["zero"]))

    if project.duration > 0:
        targets.append(SnapTarget(project.duration, "sequence_end", _PRIORITY["sequence_end"]))

    targets.append(SnapTarget(state.playhead, "playhead", _PRIORITY["playhead"]))

    if project.in_point is not None:
        targets.append(SnapTarget(float(project.in_point), "in_out", _PRIORITY["in_out"]))
    if project.out_point is not None:
        targets.append(SnapTarget(float(project.out_point), "in_out", _PRIORITY["in_out"]))

    for marker in project.markers:
        targets.append(SnapTarget(marker.time, "marker", _PRIORITY["marker"]))

    for track in project.tracks:
        if track.locked:
            continue
        if not _track_matches_scope(scope, track.type, ctx) and scope != "all":
            if scope == "same_track":
                continue
            if scope in ("video", "audio", "overlay") and track.type != scope:
                continue
        for clip in track.clips:
            if clip.id == ctx.exclude_clip_id:
                continue
            targets.append(
                SnapTarget(
                    clip.start,
                    "clip_start",
                    _clip_edge_priority(track.id, track.type, ctx),
                    track_id=track.id,
                    track_type=track.type,
                )
            )
            targets.append(
                SnapTarget(
                    clip.end,
                    "clip_end",
                    _clip_edge_priority(track.id, track.type, ctx),
                    track_id=track.id,
                    track_type=track.type,
                )
            )
            if settings.snap_to_centers:
                center = clip.start + clip.duration / 2.0
                targets.append(
                    SnapTarget(
                        center,
                        "clip_center",
                        _clip_center_priority(track.id, track.type, ctx),
                        track_id=track.id,
                        track_type=track.type,
                    )
                )

    if settings.snap_to_beats:
        targets.extend(_beat_targets(project.duration, project.bpm))

    return targets


def resolve_snap_point(
    raw_time: float,
    ctx: SnapContext,
    extra_targets: list[SnapTarget] | None = None,
) -> SnapResult:
    """Resolve one timeline position with priority and multi-guide output (S6, S18)."""
    raw_time = max(0.0, raw_time)
    if not is_snap_active(ctx):
        return SnapResult(time=max(0.0, snap(raw_time)), snapped=False)

    settings = ctx.project_state.project.snap_settings
    threshold_sec = effective_threshold_sec(settings, ctx.px_per_sec)
    targets = collect_snap_targets(ctx)
    if extra_targets:
        targets.extend(extra_targets)
    targets.extend(_frame_targets_near(raw_time, settings, ctx.px_per_sec))

    candidates: list[tuple[float, float, int, SnapTarget]] = []
    nearby: list[float] = []
    for target in targets:
        dist = abs(raw_time - target.time)
        if dist <= threshold_sec:
            candidates.append((dist, target.time, target.priority, target))
            if target.time not in nearby:
                nearby.append(target.time)

    if not candidates:
        return SnapResult(time=max(0.0, snap(raw_time)), snapped=False, nearby_guides=[])

    candidates.sort(key=lambda c: (c[0], c[2], c[1]))
    _dist, best_time, _prio, best = candidates[0]
    edge: SnapEdge = "none"
    if best.kind == "clip_start":
        edge = "start"
    elif best.kind == "clip_end":
        edge = "end"
    elif best.kind == "clip_center":
        edge = "center"

    return SnapResult(
        time=best_time,
        snapped=True,
        active_guide=best_time,
        nearby_guides=sorted(nearby),
        edge=edge,
    )


def snap_clip_move(
    raw_start: float,
    duration: float,
    ctx: SnapContext,
) -> SnapResult:
    """Snap clip move — tries start edge, end edge, and center (S17)."""
    raw_start = max(0.0, raw_start)
    if not is_snap_active(ctx):
        return SnapResult(time=max(0.0, snap(raw_start)), snapped=False, edge="none")

    ctx = SnapContext(
        project_state=ctx.project_state,
        px_per_sec=ctx.px_per_sec,
        exclude_clip_id=ctx.exclude_clip_id,
        track_id=ctx.track_id,
        track_type=ctx.track_type,
        temporary_disabled=ctx.temporary_disabled,
        clip_duration=duration,
    )

    start_result = resolve_snap_point(raw_start, ctx)
    end_result = resolve_snap_point(raw_start + duration, ctx)

    if not start_result.snapped and not end_result.snapped:
        return SnapResult(time=max(0.0, snap(raw_start)), snapped=False, edge="none")

    if end_result.snapped and (
        not start_result.snapped
        or abs((raw_start + duration) - end_result.time) < abs(raw_start - start_result.time)
    ):
        guides = list({*start_result.nearby_guides, *end_result.nearby_guides})
        return SnapResult(
            time=max(0.0, end_result.time - duration),
            snapped=True,
            active_guide=end_result.active_guide,
            nearby_guides=guides,
            edge="end",
        )

    guides = list({*start_result.nearby_guides, *end_result.nearby_guides})
    return SnapResult(
        time=max(0.0, start_result.time),
        snapped=True,
        active_guide=start_result.active_guide,
        nearby_guides=guides,
        edge="start",
    )


def snap_clip_trim(
    clip: Clip,
    side: str,
    raw_start: float,
    raw_duration: float,
    ctx: SnapContext,
) -> tuple[float, float, SnapResult]:
    if side == "trim_right":
        min_duration = 0.2
        min_end = raw_start + min_duration
        end_result = resolve_snap_point(raw_start + raw_duration, ctx)
        if end_result.snapped and end_result.time < min_end:
            duration = max(min_duration, snap(raw_duration))
            return raw_start, duration, SnapResult(
                time=raw_start + duration,
                snapped=False,
                active_guide=None,
                nearby_guides=end_result.nearby_guides,
                edge="none",
            )
        duration = max(min_duration, end_result.time - raw_start) if end_result.snapped else max(min_duration, snap(raw_duration))
        return raw_start, duration, SnapResult(
            time=raw_start + duration,
            snapped=end_result.snapped,
            active_guide=end_result.active_guide,
            nearby_guides=end_result.nearby_guides,
            edge="end" if end_result.snapped else "none",
        )

    start_result = resolve_snap_point(raw_start, ctx)
    end_fixed = raw_start + raw_duration
    if start_result.snapped:
        duration = max(0.2, end_fixed - start_result.time)
        return start_result.time, duration, start_result
    return raw_start, max(0.2, raw_duration), SnapResult(time=raw_start, snapped=False)


def snap_time(raw_time: float, ctx: SnapContext) -> SnapResult:
    return resolve_snap_point(raw_time, ctx)


# Legacy helpers for older call sites / gradual migration.
def collect_snap_times(project_state: ProjectState, **kwargs) -> list[float]:
    ctx = SnapContext(project_state=project_state, px_per_sec=project_state.project.px_per_sec, **kwargs)
    return sorted({t.time for t in collect_snap_targets(ctx)})
