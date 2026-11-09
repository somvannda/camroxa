#!/usr/bin/env python3
"""Create deterministic placeholder avatars for the sample creator pack.

These are intentionally NOT photorealistic. They keep the docs and demo data
usable until a valid SLAI key is configured. Run
``generate_sample_avatars.py`` with a working key to replace them.

Usage:
    python scripts/creator-program/make_placeholder_avatars.py --force
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "docs" / "creator-program" / "sample-creators"
CREATORS_FILE = SAMPLE_DIR / "creators.json"
AVATAR_DIR = SAMPLE_DIR / "avatars"

SIZE = 512
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, min_size: int = 20):
    size = start
    while size > min_size:
        font = load_font(size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
            return font, box
        size -= 2
    font = load_font(min_size)
    return font, draw.textbbox((0, 0), text, font=font)


def initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    return "".join(part[0].upper() for part in parts[:2]) or "C"


def gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (size, size), top)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        draw.line([(0, y), (size, y)], fill=mix(top, bottom, y / max(1, size - 1)))
    return image


def make_avatar(creator: dict) -> Image.Image:
    palette = [hex_to_rgb(color) for color in creator.get("palette", ["#7466F1", "#1B2A41", "#0A0E27"])]
    accent, mid, dark = (palette + palette)[:3]

    canvas = gradient(SIZE, mix(mid, dark, 0.25), dark)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Soft accent glow.
    for radius, alpha in ((250, 30), (190, 40), (130, 55)):
        draw.ellipse(
            [SIZE // 2 - radius, SIZE // 2 - radius - 30, SIZE // 2 + radius, SIZE // 2 + radius - 30],
            fill=(*accent, alpha),
        )

    # SAMPLE badge.
    badge_font = load_font(18)
    draw.rounded_rectangle([24, 24, 132, 60], radius=10, fill=(0, 0, 0, 120), outline=(*accent, 160), width=1)
    draw.text((40, 32), "SAMPLE", font=badge_font, fill=(*accent, 255))

    # Initials.
    text = initials(creator["display_name"])
    font, box = fit_font(draw, text, 300, 170, 72)
    text_w, text_h = box[2] - box[0], box[3] - box[1]
    draw.text(
        ((SIZE - text_w) / 2 - box[0], (SIZE - text_h) / 2 - box[1] - 42),
        text,
        font=font,
        fill=(255, 255, 255, 235),
    )

    # Name.
    name_font, name_box = fit_font(draw, creator["display_name"], 440, 42, 22)
    name_w = name_box[2] - name_box[0]
    draw.text(((SIZE - name_w) / 2 - name_box[0], 352), creator["display_name"], font=name_font, fill=(255, 255, 255, 240))

    # Category.
    category = creator.get("primary_category", "Creator")
    cat_font = load_font(24)
    cat_box = draw.textbbox((0, 0), category, font=cat_font)
    cat_w = cat_box[2] - cat_box[0]
    draw.text(((SIZE - cat_w) / 2 - cat_box[0], 404), category, font=cat_font, fill=(*accent, 240))

    # Corner mark.
    draw.text((SIZE - 108, SIZE - 38), "CAMXORA", font=load_font(14), fill=(255, 255, 255, 110))

    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite existing placeholders")
    args = parser.parse_args()

    creators = json.loads(CREATORS_FILE.read_text(encoding="utf-8"))
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)

    for creator in creators:
        destination = AVATAR_DIR / f"{creator['handle']}.png"
        if destination.exists() and not args.force:
            print(f"skip {creator['handle']}")
            continue
        make_avatar(creator).save(destination, "PNG", optimize=True)
        print(f"wrote {destination.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
