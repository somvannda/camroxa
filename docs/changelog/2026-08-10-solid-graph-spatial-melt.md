# Solid graph spatial melt (no wrap seam)

## Summary
Solid Graph used index-based gradient colors, so a closed circle put the first palette stop against the last at the join. Fill Circle already melted by screen position; Solid Graph now uses the same spatial edge coloring in preview and export.

## Surfaces
- Desktop Studio spectrum preview (`preview_widget.py`)
- Export / GPU render (`gpu_render.py`)
- Shared color engine (`spectrum_color_engine.py`)
