"""One-off port helper: python_app SpectrumPreview -> camxora_python preview_widget."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"d:\Development\Projects\Electron\MusicGenerator\python_app\views\components\_core.py")
DST = ROOT / "visualizer" / "preview_widget.py"

replacements = [
    ('from PyQt6.', 'from PySide6.'),
    ("pyqtSignal", "Signal"),
    ("from ...visualizer.gpu_render", "from visualizer.gpu_render"),
    ("from ...visualizer.audio", "from visualizer.audio"),
    ("from ...visualizer.contracts", "from visualizer.contracts"),
    (
        "from ...models.spectrum_model import default_template, normalize_template",
        "from visualizer.template_runtime import default_renderer_template, normalize_renderer_template",
    ),
    ("from ..helpers.style_helper import make_runtime_font", ""),
    ("default_template()", "default_renderer_template()"),
    ("normalize_template(", "normalize_renderer_template("),
    ("from python_app.views.helpers.style_helper import set_panel_role\n        set_panel_role(self, \"videoPreview\")\n", ""),
    ("make_runtime_font(10, QFont.Weight.Bold)", 'QFont("Segoe UI", 10, QFont.Weight.Bold)'),
    ("make_runtime_font(9)", 'QFont("Segoe UI", 9)'),
    ("from PySide6.QtCore import QSize", "from PySide6.QtCore import QSize"),
]

text = SRC.read_text(encoding="utf-8")
text = '"""Live GPU preview widget — PySide6 port of python_app SpectrumPreview."""\n\n' + text
for old, new in replacements:
    text = text.replace(old, new)
text = text.replace("class SpectrumPreview", "class VideoSpectrumPreview")
DST.write_text(text, encoding="utf-8")
print(f"Wrote {DST} ({len(text.splitlines())} lines)")
