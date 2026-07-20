"""Output resolution options shared across video/image workspaces."""

from __future__ import annotations

OUTPUT_RESOLUTION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1024x768", "Draft export (4:3) — 1024×768 — fast preview-quality"),
    ("1280x720", "Landscape 720p (16:9) — 1280×720"),
    ("1920x1080", "Landscape 1080p (16:9) — 1920×1080"),
    ("1080x1920", "Shorts/Reels (9:16) — 1080×1920"),
    ("1080x1080", "Square (1:1) — 1080×1080"),
    ("1080x1350", "Instagram Feed (4:5) — 1080×1350"),
    ("2560x1440", "QHD (16:9) — 2560×1440"),
    ("3840x2160", "4K UHD (16:9) — 3840×2160"),
)

OUTPUT_RESOLUTION_VALUES: tuple[str, ...] = tuple(value for value, _ in OUTPUT_RESOLUTION_OPTIONS)
