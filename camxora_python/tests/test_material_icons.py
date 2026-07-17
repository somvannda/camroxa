"""Tests for Material Symbol SVG rendering."""

from PySide6.QtWidgets import QApplication

from shared.icons.material_symbols import material_symbol_pixmap


def test_material_symbol_pixmap_renders(qapp: QApplication) -> None:
    pixmap = material_symbol_pixmap("videocam", color="#fbbf24", size=24)
    assert not pixmap.isNull()
    assert pixmap.width() == 24
    assert pixmap.height() == 24
