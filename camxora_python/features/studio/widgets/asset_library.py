"""Studio Asset Library browser — metadata search (doc 08)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, SUBTITLE_LABEL_ID
from visualizer.presets.metadata import ASSET_CATEGORIES, AssetMetadata, search_assets


# Map Asset Library apply → composition axis patch keys.
_APPLY_PATCH_KEYS: dict[str, str] = {
    "palette": "compositionColorPalette",
    "shape": "compositionSpectrumShape",
    "material": "compositionSpectrumMaterial",
    "animation": "compositionSpectrumAnimation",
    "particle": "compositionParticleType",
    "lighting": "compositionLightingEffect",
    "camera": "compositionCameraBehavior",
    "atmosphere": "compositionBackgroundAtmosphere",
    "background_motion": "compositionBackgroundMotion",
}


class AssetLibraryPanel(QWidget):
    apply_requested = Signal(dict)  # axis patch

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        caption = QLabel("Asset Library")
        caption.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(caption)

        filters = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("Search mood, genre, tags…")
        self._query.textChanged.connect(self._refresh)
        filters.addWidget(self._query, stretch=1)
        self._category = QComboBox()
        self._category.addItem("All", "")
        for cat in ASSET_CATEGORIES:
            self._category.addItem(cat.replace("_", " ").title(), cat)
        self._category.currentIndexChanged.connect(self._refresh)
        filters.addWidget(self._category)
        layout.addLayout(filters)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        layout.addWidget(self._list, stretch=1)

        self._detail = QLabel("Select an asset to see metadata.")
        self._detail.setObjectName(SUBTITLE_LABEL_ID)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._apply_btn = QPushButton("Apply to scene")
        self._apply_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._emit_apply)
        layout.addWidget(self._apply_btn)

        self._selected: AssetMetadata | None = None
        self._refresh()

    def _refresh(self) -> None:
        query = self._query.text()
        category = self._category.currentData() or None
        results = search_assets(query=query, category=category or None)
        self._list.clear()
        for item in results[:200]:
            row = QListWidgetItem(f"{item.name}  ·  {item.category}")
            row.setData(int(Qt.ItemDataRole.UserRole), item)
            self._list.addItem(row)
        self._selected = None
        self._apply_btn.setEnabled(False)
        self._detail.setText(f"{len(results)} asset(s)")

    def _on_select(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._selected = None
            self._apply_btn.setEnabled(False)
            return
        meta = current.data(int(Qt.ItemDataRole.UserRole))
        if not isinstance(meta, AssetMetadata):
            return
        self._selected = meta
        self._detail.setText(
            f"{meta.name}\n"
            f"Category: {meta.category}\n"
            f"Mood: {', '.join(meta.mood) or '—'}\n"
            f"Genre: {', '.join(meta.genre) or '—'}\n"
            f"Theme: {', '.join(meta.theme) or '—'}\n"
            f"Perf: {meta.performance}\n"
            f"{meta.ai_description}"
        )
        self._apply_btn.setEnabled(meta.category in _APPLY_PATCH_KEYS or meta.category == "post")

    def _emit_apply(self) -> None:
        meta = self._selected
        if meta is None:
            return
        if meta.category == "post":
            self.apply_requested.emit({"compositionPostEffectsAppend": meta.id})
            return
        key = _APPLY_PATCH_KEYS.get(meta.category)
        if key:
            self.apply_requested.emit({key: meta.id})
