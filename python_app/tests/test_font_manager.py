from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from PIL import ImageFont

from python_app.services.font_manager import FontManager


@pytest.fixture
def fonts_dir(tmp_path: Path) -> Path:
    """Create a temporary fonts directory with a dummy .ttf file."""
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    return fonts


@pytest.fixture
def sample_ttf(fonts_dir: Path) -> Path:
    """Create a minimal valid TrueType font file for testing.

    We use Pillow's built-in default font saved as a reference, but for
    unit testing we just need any .ttf file that Pillow can load.
    We'll use the system's DejaVuSans if available, otherwise skip font-load tests.
    """
    # Try common system font paths
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ]
    for c in candidates:
        if c.is_file():
            # Copy to our test dir
            dest = fonts_dir / "TestFont.ttf"
            dest.write_bytes(c.read_bytes())
            return dest

    pytest.skip("No system TrueType font found for testing")


@pytest.fixture
def sample_otf(fonts_dir: Path) -> Path:
    """Create a dummy .otf file (just for listing, not loading)."""
    otf = fonts_dir / "AnotherFont.otf"
    otf.write_bytes(b"\x00" * 100)  # Dummy data for listing
    return otf


class TestFontManagerInit:
    def test_init_sets_fonts_dir(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir))
        assert fm._fonts_dir == fonts_dir

    def test_init_with_default_font_path(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir), default_font_path="/some/font.ttf")
        assert fm._default_font_path == "/some/font.ttf"

    def test_init_without_default_font_path(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir))
        assert fm._default_font_path is None


class TestLoadFont:
    def test_load_existing_font(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir))
        font = fm.load_font(str(sample_ttf), 24)
        assert font is not None

    def test_caching_returns_same_instance(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir))
        font1 = fm.load_font(str(sample_ttf), 24)
        font2 = fm.load_font(str(sample_ttf), 24)
        assert font1 is font2

    def test_different_sizes_cached_separately(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir))
        font_24 = fm.load_font(str(sample_ttf), 24)
        font_48 = fm.load_font(str(sample_ttf), 48)
        assert font_24 is not font_48

    def test_relative_path_resolves_against_fonts_dir(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir))
        font = fm.load_font(sample_ttf.name, 24)
        assert font is not None

    def test_fallback_to_default_font(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir), default_font_path=str(sample_ttf))
        font = fm.load_font("nonexistent_font.ttf", 24)
        assert font is not None

    def test_fallback_to_builtin_when_no_default(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir))
        font = fm.load_font("nonexistent_font.ttf", 24)
        # Should not raise — falls back to Pillow's built-in font
        assert font is not None

    def test_fallback_to_builtin_when_default_also_missing(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir), default_font_path="/nonexistent/default.ttf")
        font = fm.load_font("nonexistent_font.ttf", 24)
        # Should not raise — falls back to Pillow's built-in font
        assert font is not None


class TestListAvailableFonts:
    def test_empty_directory(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir))
        assert fm.list_available_fonts() == []

    def test_lists_ttf_files(self, fonts_dir: Path, sample_ttf: Path):
        fm = FontManager(str(fonts_dir))
        result = fm.list_available_fonts()
        assert "TestFont.ttf" in result

    def test_lists_otf_files(self, fonts_dir: Path, sample_otf: Path):
        fm = FontManager(str(fonts_dir))
        result = fm.list_available_fonts()
        assert "AnotherFont.otf" in result

    def test_lists_both_ttf_and_otf(self, fonts_dir: Path, sample_ttf: Path, sample_otf: Path):
        fm = FontManager(str(fonts_dir))
        result = fm.list_available_fonts()
        assert len(result) == 2
        assert "AnotherFont.otf" in result
        assert "TestFont.ttf" in result

    def test_ignores_non_font_files(self, fonts_dir: Path):
        (fonts_dir / "readme.txt").write_text("not a font")
        (fonts_dir / "image.png").write_bytes(b"\x89PNG")
        fm = FontManager(str(fonts_dir))
        assert fm.list_available_fonts() == []

    def test_sorted_alphabetically(self, fonts_dir: Path):
        (fonts_dir / "Zebra.ttf").write_bytes(b"\x00")
        (fonts_dir / "Alpha.otf").write_bytes(b"\x00")
        (fonts_dir / "Middle.ttf").write_bytes(b"\x00")
        fm = FontManager(str(fonts_dir))
        result = fm.list_available_fonts()
        assert result == ["Alpha.otf", "Middle.ttf", "Zebra.ttf"]

    def test_nonexistent_directory(self, tmp_path: Path):
        fm = FontManager(str(tmp_path / "nonexistent"))
        assert fm.list_available_fonts() == []


class TestIsAvailable:
    def test_returns_false_for_nonexistent_dir(self, tmp_path: Path):
        fm = FontManager(str(tmp_path / "nonexistent"))
        assert fm.is_available() is False

    def test_returns_false_for_empty_dir(self, fonts_dir: Path):
        fm = FontManager(str(fonts_dir))
        assert fm.is_available() is False

    def test_returns_false_for_dir_with_only_non_font_files(self, fonts_dir: Path):
        (fonts_dir / "readme.txt").write_text("not a font")
        fm = FontManager(str(fonts_dir))
        assert fm.is_available() is False

    def test_returns_true_with_ttf_file(self, fonts_dir: Path):
        (fonts_dir / "font.ttf").write_bytes(b"\x00")
        fm = FontManager(str(fonts_dir))
        assert fm.is_available() is True

    def test_returns_true_with_otf_file(self, fonts_dir: Path):
        (fonts_dir / "font.otf").write_bytes(b"\x00")
        fm = FontManager(str(fonts_dir))
        assert fm.is_available() is True
