"""Timeline snap configuration and marker model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SnapScope = Literal["all", "same_track", "video", "audio", "overlay"]


@dataclass
class TimelineMarker:
    id: str
    time: float
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "time": self.time, "label": self.label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineMarker:
        return cls(id=data["id"], time=float(data["time"]), label=str(data.get("label", "")))


@dataclass
class SnapSettings:
    """User-facing snap preferences (S1, S11, S14, S16)."""

    enabled: bool = True
    threshold_px: float = 10.0
    scope: SnapScope = "all"
    snap_to_beats: bool = False
    snap_to_centers: bool = True
    snap_to_frames: bool = True
    click_feedback: bool = False
    frame_rate: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "threshold_px": self.threshold_px,
            "scope": self.scope,
            "snap_to_beats": self.snap_to_beats,
            "snap_to_centers": self.snap_to_centers,
            "snap_to_frames": self.snap_to_frames,
            "click_feedback": self.click_feedback,
            "frame_rate": self.frame_rate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SnapSettings:
        return cls(
            enabled=bool(data.get("enabled", True)),
            threshold_px=float(data.get("threshold_px", 10.0)),
            scope=data.get("scope", "all"),
            snap_to_beats=bool(data.get("snap_to_beats", False)),
            snap_to_centers=bool(data.get("snap_to_centers", True)),
            snap_to_frames=bool(data.get("snap_to_frames", True)),
            click_feedback=bool(data.get("click_feedback", False)),
            frame_rate=float(data.get("frame_rate", 30.0)),
        )
