"""Google Material Symbols as tinted SVG pixmaps for Qt widgets.

Icon paths from Material Symbols (https://fonts.google.com/icons).
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Material Symbols — viewBox 0 -960 960 960
MATERIAL_PATHS: dict[str, str] = {
    "monetization_on": (
        "M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763"
        "q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5"
        " 156T763-197q-54 54-127 85.5T480-80Zm0-80q134 0 227-93t93-227q0-134-93-227t-227-93"
        "q-134 0-227 93t-93 227q0 134 93 227t227 93Zm0-160q-66 0-113-47t-47-113q0-66 47-113"
        "t113-47q66 0 113 47t47 113q0 66-47 113t-113 47Zm0-80q33 0 56.5-23.5T560-480q0-33-23.5-56.5"
        "T480-560q-33 0-56.5 23.5T400-480q0 33 23.5 56.5T480-400Z"
    ),
    "music_note": (
        "M400-120v-440l520-200v440L400-120ZM160-320q-25 0-42.5-17.5T100-380q0-25 17.5-42.5"
        "T160-440q25 0 42.5 17.5T220-380q0 25-17.5 42.5T160-320Zm240 80q-25 0-42.5-17.5"
        "T340-300v-400q0-25 17.5-42.5T400-760l520-200q25 0 42.5 17.5T980-900v400q0 25-17.5"
        " 42.5T920-440l-520 200q-25 0-42.5-17.5T340-300Z"
    ),
    "image": (
        "M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760"
        "v560q0 33-23.5 56.5T760-120H200Zm0-80h560v-560H200v560Zm40-80h480L570-480 450-320"
        "l-90-120-120 160Zm260-200q25 0 42.5-17.5T520-540q0-25-17.5-42.5T460-600q-25 0-42.5"
        " 17.5T400-540q0 25 17.5 42.5T460-480Z"
    ),
    "videocam": (
        "M160-200v-560h480v80h80l120 160v320H720v80H160Zm80-80h400v-400H240v400Zm480 0v-206"
        "l-90-120H720v326Zm0 0v-326 326Z"
    ),
    "live_tv": (
        "M160-640q-33 0-56.5 23.5T80-560v280q0 33 23.5 56.5T160-200h640q33 0 56.5-23.5T880-280"
        "v-280q0-33-23.5-56.5T800-640H160Zm0 80h640v280H160v-280Zm120 120 200-120 200 120"
        "v-120H280v120Z"
    ),
    "refresh": (
        "M480-160q-134 0-227-93t-93-227q0-24 4-46.5T184-590l64 26q-6 16-9 32.5T240-520q0 100 80 180t180 80"
        "q18 0 35-2.5t34-7.5l26 64q-20 8-41.5 12.5T480-160Zm252-124-56-56 110-110H520v-80h246L656-620l56-56 200 200-200 200Z"
    ),
    "merge": (
        "M440-200h80v-167l64 63 56-57-160-160-160 160 57 56 63-62v167Zm80-360v167l-64-63-56 57 160 160 160-160-57-56-63 62v-167h-80Z"
    ),
}

ACCENT_COLORS: dict[str, str] = {
    "violet": "#a78bfa",
    "sky": "#38bdf8",
    "emerald": "#34d399",
    "amber": "#fbbf24",
    "rose": "#fb7185",
}

KPI_ICONS: dict[str, tuple[str, str]] = {
    "credits": ("monetization_on", "violet"),
    "music": ("music_note", "sky"),
    "image": ("image", "emerald"),
    "video": ("videocam", "amber"),
    "youtube": ("live_tv", "rose"),
    "merge": ("merge", "violet"),
}


def material_symbol_pixmap(name: str, *, color: str, size: int = 24) -> QPixmap:
    """Render a Material Symbol SVG path to a transparent pixmap."""
    path = MATERIAL_PATHS.get(name)
    if path is None:
        raise KeyError(f"Unknown material symbol: {name}")

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" height="{size}" width="{size}" '
        f'viewBox="0 -960 960 960">'
        f'<path fill="{color}" d="{path}"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
