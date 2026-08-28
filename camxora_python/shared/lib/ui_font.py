"""Bundled Inter for studio chrome and Khmer OS Siemreap for content."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

_FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_INTER_PATH = _FONTS_DIR / "Inter" / "Inter-Variable.ttf"
_KHMER_SIEMREAP_NAME = "Khmer OS Siemreap"
_KHMER_SIEMREAP_FILE = "KhmerOSsiemreap.ttf"

_INTER_REGISTERED = False
_KHMER_FAMILY: str | None = None


def _qt_gui_ready() -> bool:
    return QGuiApplication.instance() is not None


def ensure_inter_loaded() -> str:
    global _INTER_REGISTERED
    if _INTER_REGISTERED or not _INTER_PATH.is_file() or not _qt_gui_ready():
        return "Inter"
    QFontDatabase.addApplicationFont(str(_INTER_PATH))
    _INTER_REGISTERED = True
    return "Inter"


def _khmer_siemreap_candidates() -> tuple[Path, ...]:
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / _KHMER_SIEMREAP_FILE
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts" / _KHMER_SIEMREAP_FILE
    return (
        _FONTS_DIR / "KhmerOS" / _KHMER_SIEMREAP_FILE,
        windir,
        local,
    )


def ensure_khmer_siemreap_loaded() -> str:
    global _KHMER_FAMILY
    if _KHMER_FAMILY:
        return _KHMER_FAMILY
    if not _qt_gui_ready():
        return _KHMER_SIEMREAP_NAME
    for path in _khmer_siemreap_candidates():
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            _KHMER_FAMILY = str(families[0])
            return _KHMER_FAMILY
    _KHMER_FAMILY = _KHMER_SIEMREAP_NAME
    return _KHMER_FAMILY


def ensure_siemreap_loaded() -> str:
    return ensure_khmer_siemreap_loaded()


def studio_font(
    pixel_size: int,
    weight: QFont.Weight = QFont.Weight.Normal,
    *,
    letter_spacing: float | None = None,
    uppercase: bool = False,
) -> QFont:
    ensure_inter_loaded()
    font = QFont("Inter")
    font.setFamilies(["Inter", "Segoe UI", "Arial"])
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    if uppercase:
        font.setCapitalization(QFont.Capitalization.AllUppercase)
    if letter_spacing is not None:
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, letter_spacing)
    return font


def content_font(pixel_size: int = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Latin + Khmer body text (lyrics, titles, file names)."""
    ensure_inter_loaded()
    family = ensure_khmer_siemreap_loaded()
    fallbacks = [family, _KHMER_SIEMREAP_NAME, "Khmer OS Siem reap", "Inter", "Segoe UI", "Arial"]
    ordered: list[str] = []
    for name in fallbacks:
        if name and name not in ordered:
            ordered.append(name)
    font = QFont(ordered[0])
    font.setFamilies(ordered)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font
