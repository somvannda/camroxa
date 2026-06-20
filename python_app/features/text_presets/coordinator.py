"""TextPresetManagerCoordinator — bridges UI actions to database persistence for text style presets."""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from ...database.preset_db import (
    delete_text_style_preset,
    list_text_style_presets,
    upsert_text_style_preset,
)
from ...services.text_overlay_renderer import (
    TextStylePreset,
    render_text_overlay,
    validate_preset,
)

logger = logging.getLogger(__name__)


class TextPresetManagerCoordinator:
    """Bridges UI actions to database persistence for text style presets."""

    def __init__(self, host: Any, db_cfg: Any):
        self._host = host
        self._db_cfg = db_cfg

    def load_presets(self) -> list[dict]:
        """Load all presets for UI display."""
        return list_text_style_presets(self._db_cfg)

    def save_preset(self, preset_data: dict) -> dict:
        """Validate and persist a preset. Returns saved record or raises ValueError on invalid input."""
        preset = TextStylePreset(
            name=str(preset_data.get("name", "")).strip(),
            font_path=str(preset_data.get("font_path", "")).strip(),
            font_size=int(preset_data.get("font_size", 72)),
            primary_color=str(preset_data.get("primary_color", "#FFFFFFFF")).strip(),
            position=str(preset_data.get("position", "center")).strip(),
            glow_color=str(preset_data.get("glow_color", "#00000000")).strip(),
            glow_radius=int(preset_data.get("glow_radius", 0)),
            shadow_offset_x=int(preset_data.get("shadow_offset_x", 0)),
            shadow_offset_y=int(preset_data.get("shadow_offset_y", 0)),
            shadow_color=str(preset_data.get("shadow_color", "#00000080")).strip(),
            stroke_width=int(preset_data.get("stroke_width", 0)),
            stroke_color=str(preset_data.get("stroke_color", "#000000FF")).strip(),
            gradient_enabled=bool(preset_data.get("gradient_enabled", False)),
            gradient_start_color=str(preset_data.get("gradient_start_color", "#FFFFFFFF")).strip(),
            gradient_end_color=str(preset_data.get("gradient_end_color", "#000000FF")).strip(),
            line_spacing=float(preset_data.get("line_spacing", 1.4)),
            alignment=str(preset_data.get("alignment", "center")).strip(),
            max_text_width_pct=int(preset_data.get("max_text_width_pct", 80)),
            vertical_padding_pct=int(preset_data.get("vertical_padding_pct", 10)),
        )

        errors = validate_preset(preset)
        if errors:
            raise ValueError("; ".join(errors))

        return upsert_text_style_preset(self._db_cfg, preset_data)

    def delete_preset(self, preset_id: int) -> None:
        """Delete a preset from the database."""
        delete_text_style_preset(self._db_cfg, preset_id)

    def render_preview(
        self, preset_data: dict, sample_text: str, width: int, height: int
    ) -> Image.Image:
        """Render a preview image for the UI form."""
        preset = TextStylePreset(
            name=str(preset_data.get("name", "Preview")).strip() or "Preview",
            font_path=str(preset_data.get("font_path", "")).strip(),
            font_size=int(preset_data.get("font_size", 72)),
            primary_color=str(preset_data.get("primary_color", "#FFFFFFFF")).strip(),
            position=str(preset_data.get("position", "center")).strip(),
            glow_color=str(preset_data.get("glow_color", "#00000000")).strip(),
            glow_radius=int(preset_data.get("glow_radius", 0)),
            shadow_offset_x=int(preset_data.get("shadow_offset_x", 0)),
            shadow_offset_y=int(preset_data.get("shadow_offset_y", 0)),
            shadow_color=str(preset_data.get("shadow_color", "#00000080")).strip(),
            stroke_width=int(preset_data.get("stroke_width", 0)),
            stroke_color=str(preset_data.get("stroke_color", "#000000FF")).strip(),
            gradient_enabled=bool(preset_data.get("gradient_enabled", False)),
            gradient_start_color=str(preset_data.get("gradient_start_color", "#FFFFFFFF")).strip(),
            gradient_end_color=str(preset_data.get("gradient_end_color", "#000000FF")).strip(),
            line_spacing=float(preset_data.get("line_spacing", 1.4)),
            alignment=str(preset_data.get("alignment", "center")).strip(),
            max_text_width_pct=int(preset_data.get("max_text_width_pct", 80)),
            vertical_padding_pct=int(preset_data.get("vertical_padding_pct", 10)),
        )

        titles = [sample_text] if sample_text else []
        return render_text_overlay(titles, preset, width, height)

    def has_presets(self) -> bool:
        """Check if at least one preset exists (for mode switch validation)."""
        presets = list_text_style_presets(self._db_cfg)
        return len(presets) > 0
