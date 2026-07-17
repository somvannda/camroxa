"""Visualizer DTO contracts.

Defines immutable data-transfer objects used to communicate between the
app shell / feature coordinators and the visualizer subsystem.  These DTOs
form the hardened boundary described in Requirement 12.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RenderRequest:
    """DTO passed from app shell / coordinators into the visualizer."""

    audio_path: str
    output_path: str
    width: int
    height: int
    fps: int = 30
    template: dict = field(default_factory=dict)
    background_path: str = ""
    logo_path: str = ""
    duration_sec: float = 0.0


@dataclass(frozen=True)
class PreviewConfig:
    """DTO for configuring the live preview widget."""

    width: int
    height: int
    template: dict = field(default_factory=dict)
    background_path: str = ""
    logo_path: str = ""


@dataclass(frozen=True)
class RenderProgress:
    """DTO emitted by the visualizer during rendering."""

    frame: int
    total_frames: int
    percent: float
    elapsed_sec: float


@dataclass(frozen=True)
class RenderResult:
    """DTO returned when rendering completes."""

    success: bool
    output_path: str
    duration_sec: float
    error: str = ""
