"""Shared coordinator types for the enterprise architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GenerationRequest:
    """Canonical music generation request shape."""

    songs: list[dict]
    settings: dict
    batch_mode: str  # "single" | "batch" | "auto"
    profile_id: str = ""


@dataclass(frozen=True)
class ImageJobRequest:
    """Canonical image generation job request."""

    batch_id: str
    profile_id: str
    role: str  # "background" | "thumbnail"
    prompt: str
    provider: str  # "slai" | "openai"
    dimensions: tuple[int, int] = (1920, 1080)


@dataclass(frozen=True)
class PollResult:
    """Result from an image generation poll."""

    job_uid: str
    status: str  # "pending" | "running" | "done" | "failed"
    image_url: str = ""
    error: str = ""
