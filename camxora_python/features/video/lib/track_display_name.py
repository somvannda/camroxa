"""Clean Suno / Camxora download filenames into display titles."""

from __future__ import annotations

import re
from pathlib import Path

# Design-system suffixes appended when downloading from Suno.
_VARIANT_SUFFIXES = (
    "OK",
    "ATL",
    "Alt",
    "ALT",
    "Primary",
    "Secondary",
)

_VARIANT_RE = re.compile(
    r"(?:_|\s)+(?:" + "|".join(_VARIANT_SUFFIXES) + r")$",
    re.IGNORECASE,
)
_TRACK_PREFIX_RE = re.compile(r"^\s*\d+\.\s*")
_WEBGPU_TAIL_RE = re.compile(r"(?:_|\s)+WEBGPU(?:_\d{8}-\d{6})?$", re.IGNORECASE)


def clean_track_display_name(raw: str, *, keep_track_number: bool = False) -> str:
    """Turn ``10. Song Title_OK.mp3`` into ``Song Title`` (or keep ``10.`` if asked)."""
    stem = Path(str(raw or "").strip()).stem if str(raw or "").strip() else ""
    if not stem:
        return ""
    name = _WEBGPU_TAIL_RE.sub("", stem).strip()
    name = _VARIANT_RE.sub("", name).strip()
    if not keep_track_number:
        name = _TRACK_PREFIX_RE.sub("", name).strip()
    return name or stem


def track_titles_from_paths(paths: list[str] | tuple[str, ...] | None) -> list[str]:
    titles: list[str] = []
    for path in paths or []:
        title = clean_track_display_name(str(path or ""))
        if title:
            titles.append(title)
    return titles


def format_title_marker(
    index: int,
    style: str,
    *,
    total: int | None = None,
    indent: str = "aligned",
) -> str:
    """Prefix for a title row. ``index`` is 0-based.

    ``indent``:
    - ``aligned`` — pad markers so title text starts on one vertical line
      (hanging indent). Fixes the staggered ``1.`` vs ``10.`` look.
    - ``flush`` — natural marker width (ragged left edge).
    """
    key = str(style or "number").strip().lower()
    indent_key = str(indent or "aligned").strip().lower()
    n = max(1, int(index) + 1)
    if key in ("none", "plain", ""):
        return ""
    if key in ("bullet", "dot"):
        return "• "
    if key in ("dash",):
        return "– "
    if key in ("number_pad", "padded"):
        marker = f"{n:02d}. "
        # Already fixed-width digits; aligned/flush look the same.
        return marker
    # default: number
    if indent_key == "flush":
        return f"{n}. "
    # Aligned / hanging: zero-pad to the widest index so title text shares
    # one vertical start line in any proportional font (1→01 when total≥10).
    max_n = max(n, int(total or n))
    width = max(1, len(str(max_n)))
    return f"{n:0{width}d}. "
