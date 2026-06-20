"""Generate a multi-resolution Windows .ico from the app SVG logo.

Renders python_app/assets/icons/electric-guitar.svg to high-res PNG via Qt,
then writes python_app/assets/icons/app.ico containing the standard icon
sizes Windows uses (16/24/32/48/64/128/256).

Run:  python tools/make_icon.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Offscreen so no display is required.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtCore import Qt
from PyQt6.QtSvg import QSvgRenderer
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "python_app" / "assets" / "icons" / "electric-guitar.svg"
OUT_ICO = ROOT / "python_app" / "assets" / "icons" / "app.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_svg_to_png(svg_path: Path, px: int) -> Image.Image:
    renderer = QSvgRenderer(str(svg_path))
    img = QImage(px, px, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    # Convert QImage -> PIL Image (RGBA)
    img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(height * width * 4)
    return Image.frombytes("RGBA", (width, height), bytes(ptr))


def main() -> int:
    if not SVG.exists():
        print(f"ERROR: SVG not found: {SVG}")
        return 1
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    # Render the largest size once, then let Pillow downscale for crisp results.
    base = render_svg_to_png(SVG, 256)
    icons = [base.resize((s, s), Image.Resampling.LANCZOS) for s in SIZES]
    base.save(str(OUT_ICO), format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Wrote {OUT_ICO} with sizes {SIZES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
