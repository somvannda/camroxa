from __future__ import annotations

import logging
from pathlib import Path

from PIL import ImageFont

logger = logging.getLogger(__name__)

_FONT_EXTENSIONS = (".ttf", ".otf")


class FontManager:
    """Loads and caches fonts from a configurable directory."""

    def __init__(self, fonts_dir: str, default_font_path: str | None = None):
        self._fonts_dir = Path(fonts_dir)
        self._default_font_path = default_font_path
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def load_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        """Load font at given size. Falls back to default if font_path not found."""
        key = (font_path, size)
        if key in self._cache:
            return self._cache[key]

        resolved = Path(font_path)
        if not resolved.is_absolute():
            resolved = self._fonts_dir / font_path

        if resolved.is_file():
            font = ImageFont.truetype(str(resolved), size)
            self._cache[key] = font
            return font

        # Fallback: try the configured default font path
        if self._default_font_path:
            default_key = (self._default_font_path, size)
            if default_key in self._cache:
                self._cache[key] = self._cache[default_key]
                return self._cache[key]

            default_resolved = Path(self._default_font_path)
            if default_resolved.is_file():
                logger.warning(
                    "Font not found at '%s', falling back to default: %s",
                    font_path,
                    self._default_font_path,
                )
                font = ImageFont.truetype(str(default_resolved), size)
                self._cache[key] = font
                self._cache[default_key] = font
                return font

        # Final fallback: Pillow's built-in default sans-serif font
        logger.warning(
            "Font not found at '%s' and no default configured, using Pillow built-in font",
            font_path,
        )
        font = ImageFont.load_default(size)
        self._cache[key] = font
        return font

    def list_available_fonts(self) -> list[str]:
        """List .ttf and .otf files in the fonts directory."""
        if not self._fonts_dir.is_dir():
            return []

        fonts: list[str] = []
        for p in self._fonts_dir.iterdir():
            if p.is_file() and p.suffix.lower() in _FONT_EXTENSIONS:
                fonts.append(p.name)
        fonts.sort()
        return fonts

    def is_available(self) -> bool:
        """Returns True if fonts directory exists and has at least one font file."""
        if not self._fonts_dir.is_dir():
            return False

        for p in self._fonts_dir.iterdir():
            if p.is_file() and p.suffix.lower() in _FONT_EXTENSIONS:
                return True
        return False
