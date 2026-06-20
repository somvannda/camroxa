from __future__ import annotations


def output_resolution_presets() -> list[tuple[str, str]]:
    return [
        ("Landscape 720p (16:9) — 1280×720", "1280x720"),
        ("Landscape 1080p (16:9) — 1920×1080", "1920x1080"),
        ("Shorts/Reels (9:16) — 1080×1920", "1080x1920"),
        ("Square (1:1) — 1080×1080", "1080x1080"),
        ("Instagram Feed (4:5) — 1080×1350", "1080x1350"),
        ("QHD (16:9) — 2560×1440", "2560x1440"),
        ("4K UHD (16:9) — 3840×2160", "3840x2160"),
    ]

