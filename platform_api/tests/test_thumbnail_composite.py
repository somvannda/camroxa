from __future__ import annotations

from io import BytesIO

from PIL import Image

from platform_api.services.thumbnail_composite import (
    build_thumbnail_overlay_input_png,
    compose_thumbnail_onto_background,
    enrich_background_prompt,
    enrich_thumbnail_prompt,
    normalize_thumbnail_reference_mode,
)


def test_normalize_thumbnail_reference_mode_defaults_to_composite() -> None:
    assert normalize_thumbnail_reference_mode(None) == "composite"
    assert normalize_thumbnail_reference_mode("dual_reference") == "dual_reference"
    assert normalize_thumbnail_reference_mode("unknown") == "composite"


def test_enrich_prompts_add_expected_instructions() -> None:
    background = enrich_background_prompt("Dark city skyline")
    thumbnail = enrich_thumbnail_prompt("Bold track list")
    assert "do not generate any text" in background.lower()
    assert "pure black background" in thumbnail.lower()


def test_build_thumbnail_overlay_input_png_contains_style_box() -> None:
    image = Image.new("RGBA", (200, 100), (255, 220, 40, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        style_path = Path(tmp) / "style.png"
        style_path.write_bytes(buffer.getvalue())
        overlay_input = build_thumbnail_overlay_input_png(str(style_path), "1920x1080", 0.8)
        composed = Image.open(BytesIO(overlay_input)).convert("RGBA")
        assert composed.size == (1920, 1080)


def test_compose_thumbnail_onto_background(tmp_path) -> None:
    background = tmp_path / "bg.png"
    Image.new("RGB", (1920, 1080), (20, 40, 120)).save(background)
    overlay = Image.new("RGBA", (1920, 1080), (255, 220, 40, 255))
    overlay_buffer = BytesIO()
    overlay.save(overlay_buffer, format="PNG")

    result = compose_thumbnail_onto_background(
        background_path=str(background),
        overlay_png_bytes=overlay_buffer.getvalue(),
        resolution="1920x1080",
        style_strength=0.8,
    )
    final = Image.open(BytesIO(result))
    assert final.size == (1920, 1080)
