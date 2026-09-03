"""Structured diagnostics for preview drag — shape/size drift during move."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger("camxora.preview.drag")

# Set CAMXORA_DRAG_LOG=1 to force INFO-level drag traces (default follows DEBUG).
_FORCE_INFO = os.environ.get("CAMXORA_DRAG_LOG", "").strip().lower() in ("1", "true", "yes")


def _emit(level: int, msg: str, *args: Any) -> None:
    if _FORCE_INFO and level == logging.DEBUG:
        level = logging.INFO
    logger.log(level, msg, *args)


def _aspect(w: float, h: float) -> float | None:
    if h <= 0:
        return None
    return w / h


def format_norm_rect(
    norm: dict[str, float] | None,
    *,
    canvas_w: int = 0,
    canvas_h: int = 0,
) -> str:
    if not norm:
        return "norm=<empty>"
    x = float(norm.get("x", 0))
    y = float(norm.get("y", 0))
    w = float(norm.get("w", 0))
    h = float(norm.get("h", 0))
    px_w = int(round(w * canvas_w)) if canvas_w > 0 else 0
    px_h = int(round(h * canvas_h)) if canvas_h > 0 else 0
    asp = _aspect(px_w, px_h)
    asp_s = f"{asp:.4f}" if asp is not None else "n/a"
    return (
        f"norm=({x:.4f},{y:.4f},{w:.4f},{h:.4f}) "
        f"px=({px_w}x{px_h}) aspect={asp_s}"
    )


def format_widget_rect(rect: Any | None) -> str:
    if rect is None or getattr(rect, "isEmpty", lambda: True)():
        return "widget=<empty>"
    w = int(rect.width())
    h = int(rect.height())
    asp = _aspect(w, h)
    asp_s = f"{asp:.4f}" if asp is not None else "n/a"
    return f"widget=({rect.x()},{rect.y()},{w}x{h}) aspect={asp_s}"


def log_drag_event(
    event: str,
    *,
    comp_id: str | None = None,
    norm: dict[str, float] | None = None,
    canvas_w: int = 0,
    canvas_h: int = 0,
    widget_rect: Any | None = None,
    stored_layout: dict[str, float] | None = None,
    detail: str = "",
) -> None:
    parts = [f"drag {event}"]
    if comp_id:
        parts.append(f"comp={comp_id}")
    if norm is not None:
        parts.append(format_norm_rect(norm, canvas_w=canvas_w, canvas_h=canvas_h))
    if widget_rect is not None:
        parts.append(format_widget_rect(widget_rect))
    if stored_layout:
        parts.append(f"stored={dict(stored_layout)}")
    if detail:
        parts.append(detail)
    _emit(logging.DEBUG, " | ".join(parts))


class DragShapeWatch:
    """Tracks baseline rect and warns when w/h or aspect drift during drag."""

    def __init__(self) -> None:
        self._baseline_norm: dict[str, float] | None = None
        self._baseline_widget: tuple[int, int, int, int] | None = None
        self._move_count = 0
        self._last_log_ts = 0.0
        self._drift_warnings = 0

    def reset(
        self,
        norm: dict[str, float],
        widget_rect: Any | None = None,
    ) -> None:
        self._baseline_norm = dict(norm)
        if widget_rect is not None and not widget_rect.isEmpty():
            self._baseline_widget = (
                int(widget_rect.x()),
                int(widget_rect.y()),
                int(widget_rect.width()),
                int(widget_rect.height()),
            )
        else:
            self._baseline_widget = None
        self._move_count = 0
        self._last_log_ts = 0.0
        self._drift_warnings = 0

    def clear(self) -> None:
        self._baseline_norm = None
        self._baseline_widget = None
        self._move_count = 0

    def check_move(
        self,
        norm: dict[str, float],
        *,
        canvas_w: int,
        canvas_h: int,
        widget_rect: Any | None = None,
        comp_id: str = "song_list",
    ) -> None:
        self._move_count += 1
        base = self._baseline_norm
        if base is None:
            return

        w_delta = abs(float(norm.get("w", 0)) - float(base.get("w", 0)))
        h_delta = abs(float(norm.get("h", 0)) - float(base.get("h", 0)))
        shape_drift = w_delta > 1e-5 or h_delta > 1e-5

        widget_drift = False
        widget_detail = ""
        if widget_rect is not None and self._baseline_widget is not None and not widget_rect.isEmpty():
            bx, by, bw, bh = self._baseline_widget
            ww = int(widget_rect.width())
            wh = int(widget_rect.height())
            if abs(ww - bw) > 1 or abs(wh - bh) > 1:
                widget_drift = True
                widget_detail = f"widget_size {bw}x{bh} -> {ww}x{wh}"

        now = time.monotonic()
        should_sample = (now - self._last_log_ts) >= 0.15  # ~6 traces/sec while moving

        if shape_drift or widget_drift:
            self._drift_warnings += 1
            _emit(
                logging.WARNING,
                "drag SHAPE DRIFT #%s move=%s comp=%s | baseline %s | current %s | %s %s",
                self._drift_warnings,
                self._move_count,
                comp_id,
                format_norm_rect(base, canvas_w=canvas_w, canvas_h=canvas_h),
                format_norm_rect(norm, canvas_w=canvas_w, canvas_h=canvas_h),
                format_widget_rect(widget_rect),
                widget_detail,
            )
        elif should_sample:
            self._last_log_ts = now
            log_drag_event(
                "move",
                comp_id=comp_id,
                norm=norm,
                canvas_w=canvas_w,
                canvas_h=canvas_h,
                widget_rect=widget_rect,
                detail=f"move#{self._move_count} pos=({norm.get('x', 0):.4f},{norm.get('y', 0):.4f})",
            )

    def summary(self, comp_id: str = "song_list") -> None:
        if self._move_count <= 0:
            return
        _emit(
            logging.INFO,
            "drag END comp=%s moves=%s shape_drift_warnings=%s",
            comp_id,
            self._move_count,
            self._drift_warnings,
        )


def log_layout_resolve(
    *,
    sub_template: str,
    canvas_w: int,
    canvas_h: int,
    custom: dict[str, float] | None,
    resolved: dict[str, float],
    caller: str,
) -> None:
    _emit(
        logging.DEBUG,
        "layout resolve caller=%s sub=%s canvas=%sx%s custom=%s -> %s",
        caller,
        sub_template,
        canvas_w,
        canvas_h,
        dict(custom) if custom else None,
        format_norm_rect(resolved, canvas_w=canvas_w, canvas_h=canvas_h),
    )


def log_render_rect(
    *,
    sub_template: str,
    canvas_w: int,
    canvas_h: int,
    norm: dict[str, float],
    px: tuple[int, int, int, int],
    ref_w: int | None = None,
    ref_h: int | None = None,
) -> None:
    x, y, w, h = px
    ref_aspect = _aspect(ref_w or 0, ref_h or 0)
    px_aspect = _aspect(w, h)
    stretch = "ok"
    if ref_aspect and px_aspect:
        ratio = px_aspect / ref_aspect
        if abs(ratio - 1.0) > 0.02:
            stretch = f"STRETCHED ratio={ratio:.4f} ref_aspect={ref_aspect:.4f}"
    _emit(
        logging.DEBUG,
        "render song_list sub=%s canvas=%sx%s %s px=(%s,%s,%s,%s) ref=%sx%s %s",
        sub_template,
        canvas_w,
        canvas_h,
        format_norm_rect(norm, canvas_w=canvas_w, canvas_h=canvas_h),
        x,
        y,
        w,
        h,
        ref_w or "?",
        ref_h or "?",
        stretch,
    )
