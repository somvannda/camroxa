"""Broadcast when the local video template catalog changes.

Settings profile dropdowns and other shells subscribe so create/save/delete
and marketplace installs refresh without remounting pages.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class VideoTemplateCatalogBus(QObject):
    changed = Signal()

    _instance: VideoTemplateCatalogBus | None = None

    @classmethod
    def instance(cls) -> VideoTemplateCatalogBus:
        if cls._instance is None:
            cls._instance = VideoTemplateCatalogBus()
        return cls._instance


def emit_video_template_catalog_changed() -> None:
    VideoTemplateCatalogBus.instance().changed.emit()
