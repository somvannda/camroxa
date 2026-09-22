"""Playlist typography font catalog and TTF path resolution for Pillow."""

from __future__ import annotations

import os
import sys
from functools import lru_cache

from PIL import ImageFont

DEFAULT_PLAYLIST_FONT = "Segoe UI"

PLAYLIST_FONT_VARIANTS: tuple[str, ...] = ("normal", "bold", "italic", "bold_italic")
PLAYLIST_FONT_VARIANT_LABELS: dict[str, str] = {
    "normal": "Normal",
    "bold": "Bold",
    "italic": "Italic",
    "bold_italic": "Bold italic",
}

# (stored id, display name) — shown in Typography → Font
PLAYLIST_FONT_CHOICES: tuple[tuple[str, str], ...] = (
    ("segoe-ui", "Segoe UI"),
    ("arial", "Arial"),
    ("calibri", "Calibri"),
    ("georgia", "Georgia"),
    ("times-new-roman", "Times New Roman"),
    ("verdana", "Verdana"),
    ("tahoma", "Tahoma"),
    ("courier-new", "Courier New"),
    ("consolas", "Consolas"),
    ("cambria", "Cambria"),
    ("trebuchet-ms", "Trebuchet MS"),
    ("impact", "Impact"),
)

_CHOICE_BY_ID: dict[str, str] = dict(PLAYLIST_FONT_CHOICES)
_CHOICE_BY_NAME: dict[str, str] = {name.lower(): fid for fid, name in PLAYLIST_FONT_CHOICES}

_WINDOWS_FILES: dict[str, dict[str, tuple[str, ...]]] = {
    "Segoe UI": {
        "normal": ("segoeui.ttf", "SegoeUI.ttf"),
        "bold": ("segoeuib.ttf", "SegoeUI-Bold.ttf"),
        "italic": ("segoeuii.ttf", "SegoeUI-Italic.ttf"),
        "bold_italic": ("segoeuiz.ttf", "SegoeUI-BoldItalic.ttf"),
    },
    "Arial": {
        "normal": ("arial.ttf",),
        "bold": ("arialbd.ttf",),
        "italic": ("ariali.ttf",),
        "bold_italic": ("arialbi.ttf",),
    },
    "Calibri": {
        "normal": ("calibri.ttf",),
        "bold": ("calibrib.ttf",),
        "italic": ("calibrii.ttf",),
        "bold_italic": ("calibriz.ttf",),
    },
    "Georgia": {
        "normal": ("georgia.ttf",),
        "bold": ("georgiab.ttf",),
        "italic": ("georgiai.ttf",),
        "bold_italic": ("georgiaz.ttf",),
    },
    "Times New Roman": {
        "normal": ("times.ttf",),
        "bold": ("timesbd.ttf",),
        "italic": ("timesi.ttf",),
        "bold_italic": ("timesbi.ttf",),
    },
    "Verdana": {
        "normal": ("verdana.ttf",),
        "bold": ("verdanab.ttf",),
        "italic": ("verdanai.ttf",),
        "bold_italic": ("verdanaz.ttf",),
    },
    "Tahoma": {
        "normal": ("tahoma.ttf",),
        "bold": ("tahomabd.ttf",),
        "italic": ("tahoma.ttf",),
        "bold_italic": ("tahomabd.ttf",),
    },
    "Courier New": {
        "normal": ("cour.ttf",),
        "bold": ("courbd.ttf",),
        "italic": ("couri.ttf",),
        "bold_italic": ("courbi.ttf",),
    },
    "Consolas": {
        "normal": ("consola.ttf",),
        "bold": ("consolab.ttf",),
        "italic": ("consolai.ttf",),
        "bold_italic": ("consolaz.ttf",),
    },
    "Cambria": {
        "normal": ("cambria.ttc",),
        "bold": ("cambriab.ttf",),
        "italic": ("cambriai.ttf",),
        "bold_italic": ("cambriaz.ttf",),
    },
    "Trebuchet MS": {
        "normal": ("trebuc.ttf",),
        "bold": ("trebucbd.ttf",),
        "italic": ("trebucit.ttf",),
        "bold_italic": ("trebucbi.ttf",),
    },
    "Impact": {
        "normal": ("impact.ttf",),
        "bold": ("impact.ttf",),
        "italic": ("impact.ttf",),
        "bold_italic": ("impact.ttf",),
    },
}

# Legacy flat map for fallback lookups
_WINDOWS_FILES_FLAT: dict[str, tuple[str, ...]] = {
    "Segoe UI": ("segoeui.ttf", "SegoeUI.ttf"),
    "Arial": ("arial.ttf",),
    "Calibri": ("calibri.ttf",),
    "Georgia": ("georgia.ttf",),
    "Times New Roman": ("times.ttf", "timesbd.ttf"),
    "Verdana": ("verdana.ttf",),
    "Tahoma": ("tahoma.ttf",),
    "Courier New": ("cour.ttf",),
    "Consolas": ("consola.ttf",),
    "Cambria": ("cambria.ttc",),
    "Trebuchet MS": ("trebuc.ttf",),
    "Impact": ("impact.ttf",),
}

_DARWIN_FILES: dict[str, tuple[str, ...]] = {
    "Segoe UI": ("Helvetica.ttc", "Arial.ttf"),
    "Arial": ("Arial.ttf",),
    "Calibri": ("Calibri.ttf",),
    "Georgia": ("Georgia.ttf",),
    "Times New Roman": ("Times New Roman.ttf", "Times.ttc"),
    "Verdana": ("Verdana.ttf",),
    "Tahoma": ("Tahoma.ttf",),
    "Courier New": ("Courier New.ttf",),
    "Consolas": ("Consolas.ttf",),
    "Cambria": ("Cambria.ttf",),
    "Trebuchet MS": ("Trebuchet MS.ttf",),
    "Impact": ("Impact.ttf",),
}

_LINUX_FILES: dict[str, tuple[str, ...]] = {
    "Segoe UI": ("DejaVuSans.ttf",),
    "Arial": ("DejaVuSans.ttf", "LiberationSans-Regular.ttf"),
    "Calibri": ("DejaVuSans.ttf",),
    "Georgia": ("DejaVuSerif.ttf",),
    "Times New Roman": ("DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"),
    "Verdana": ("DejaVuSans.ttf",),
    "Tahoma": ("DejaVuSans.ttf",),
    "Courier New": ("DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"),
    "Consolas": ("DejaVuSansMono.ttf",),
    "Cambria": ("DejaVuSerif.ttf",),
    "Trebuchet MS": ("DejaVuSans.ttf",),
    "Impact": ("DejaVuSans-Bold.ttf",),
}

_FALLBACK_FILES: tuple[str, ...] = (
    "segoeui.ttf",
    "arial.ttf",
    "DejaVuSans.ttf",
)


def normalize_font_family(value: str | None) -> str:
    if not value:
        return DEFAULT_PLAYLIST_FONT
    if value in _CHOICE_BY_ID:
        return _CHOICE_BY_ID[value]
    for _fid, name in PLAYLIST_FONT_CHOICES:
        if name.lower() == value.lower():
            return name
    return value


def font_choice_index(family: str) -> int:
    family = normalize_font_family(family)
    for index, (_fid, name) in enumerate(PLAYLIST_FONT_CHOICES):
        if name.lower() == family.lower():
            return index
    return 0


def _platform_map() -> dict[str, tuple[str, ...]]:
    if sys.platform == "darwin":
        return _DARWIN_FILES
    if sys.platform.startswith("linux"):
        return _LINUX_FILES
    return _WINDOWS_FILES


def _fonts_dir() -> str:
    return os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")


def _mac_font_dirs() -> list[str]:
    return [
        "/System/Library/Fonts/Supplemental",
        "/System/Library/Fonts",
        "/Library/Fonts",
    ]


def _linux_font_dirs() -> list[str]:
    return [
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/usr/local/share/fonts",
    ]


def normalize_font_variant(value: str | None) -> str:
    variant = (value or "normal").lower().replace("-", "_")
    if variant not in PLAYLIST_FONT_VARIANTS:
        return "normal"
    return variant


def font_variant_index(variant: str) -> int:
    variant = normalize_font_variant(variant)
    for index, key in enumerate(PLAYLIST_FONT_VARIANTS):
        if key == variant:
            return index
    return 0


def _platform_variant_map() -> dict[str, dict[str, tuple[str, ...]]]:
    if sys.platform == "darwin":
        return _DARWIN_FILES  # type: ignore[return-value]
    if sys.platform.startswith("linux"):
        return _LINUX_FILES  # type: ignore[return-value]
    return _WINDOWS_FILES


def _candidate_paths(family: str, variant: str = "normal") -> list[str]:
    family = normalize_font_family(family)
    variant = normalize_font_variant(variant)
    platform_map = _platform_variant_map()
    family_variants = platform_map.get(family)
    if isinstance(family_variants, dict):
        platform_files = family_variants.get(variant) or family_variants.get("normal", ())
    else:
        platform_files = family_variants or _WINDOWS_FILES_FLAT.get(family, ())
    paths: list[str] = []

    if sys.platform == "win32":
        fonts_dir = _fonts_dir()
        for filename in platform_files:
            paths.append(os.path.join(fonts_dir, filename))
    elif sys.platform == "darwin":
        for directory in _mac_font_dirs():
            for filename in platform_files:
                paths.append(os.path.join(directory, filename))
    else:
        for directory in _linux_font_dirs():
            for filename in platform_files:
                paths.append(os.path.join(directory, filename))

    if sys.platform == "win32":
        for filename in _FALLBACK_FILES:
            paths.append(os.path.join(_fonts_dir(), filename))
    else:
        paths.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
        )
    return paths


@lru_cache(maxsize=64)
def resolve_playlist_font_path(family: str, variant: str = "normal") -> str | None:
    for path in _candidate_paths(family, variant):
        if path and os.path.isfile(path):
            return path
    if normalize_font_variant(variant) != "normal":
        for path in _candidate_paths(family, "normal"):
            if path and os.path.isfile(path):
                return path
    return None


@lru_cache(maxsize=256)
def playlist_font(
    family: str,
    size_px: int,
    variant: str = "normal",
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = resolve_playlist_font_path(family, variant)
    if path is not None:
        try:
            return ImageFont.truetype(path, max(8, size_px))
        except OSError:
            pass
    return ImageFont.load_default()


def playlist_font_fn(family: str, variant: str = "normal"):
    """Return a size-only callable for track-list renderers."""
    normalized = normalize_font_family(family)
    normalized_variant = normalize_font_variant(variant)

    def _load(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        return playlist_font(normalized, size_px, normalized_variant)

    return _load


def playlist_row_font_loaders(typography) -> tuple:
    """Header, title, and meta font loaders for a track-list card."""
    family = normalize_font_family(getattr(typography, "font_family", DEFAULT_PLAYLIST_FONT))
    title_variant = normalize_font_variant(getattr(typography, "song_title_variant", "normal"))
    meta_variant = normalize_font_variant(getattr(typography, "song_meta_variant", "normal"))
    return (
        playlist_font_fn(family, "normal"),
        playlist_font_fn(family, title_variant),
        playlist_font_fn(family, meta_variant),
    )
