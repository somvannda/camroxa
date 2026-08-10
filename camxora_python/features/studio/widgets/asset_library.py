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
from visualizer_studio.presets.metadata import ASSET_CATEGORIES, AssetMetadata, search_assets

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
    "post": "compositionPostEffectsAppend",
}

# Scene tree node → preferred catalog category for context-aware browse.
_NODE_CATEGORY: dict[str, str] = {
    "palette": "palette",
    "background": "atmosphere",
    "spectrum": "shape",
    "logo": "animation",
    "particles": "particle",
    "lighting": "lighting",
    "camera": "camera",
    "post": "post",
    "overlay": "animation",
}


class AssetLibraryPanel(QWidget):
    apply_requested = Signal(dict)  # axis patch
    favorite_toggled = Signal(str, bool)  # asset id, favorite

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        caption = QLabel("Asset Library — search by mood / genre / tags")
        caption.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(caption)

        filters = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("Search…")
        self._query.textChanged.connect(self._refresh)
        filters.addWidget(self._query, stretch=1)
        self._category = QComboBox()
        self._category.addItem("All", "")
        for cat in ASSET_CATEGORIES:
            self._category.addItem(cat.replace("_", " ").title(), cat)
        self._category.currentIndexChanged.connect(self._refresh)
        filters.addWidget(self._category)
        layout.addLayout(filters)

        meta = QHBoxLayout()
        self._mood = QComboBox()
        self._mood.addItem("Any mood", "")
        for mood in ("Energetic", "Aggressive", "Dreamy", "Dark", "Epic", "Calm"):
            self._mood.addItem(mood, mood)
        self._mood.currentIndexChanged.connect(self._refresh)
        meta.addWidget(self._mood)
        self._genre = QComboBox()
        self._genre.addItem("Any genre", "")
        for genre in ("EDM", "Trap", "Synthwave", "Pop", "Dubstep"):
            self._genre.addItem(genre, genre)
        self._genre.currentIndexChanged.connect(self._refresh)
        meta.addWidget(self._genre)
        self._perf = QComboBox()
        self._perf.addItem("Any perf", "")
        for perf in ("low", "medium", "high"):
            self._perf.addItem(perf.title(), perf)
        self._perf.currentIndexChanged.connect(self._refresh)
        meta.addWidget(self._perf)
        layout.addLayout(meta)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        layout.addWidget(self._list, stretch=1)

        self._detail = QLabel("Select an asset to see metadata.")
        self._detail.setObjectName(SUBTITLE_LABEL_ID)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        actions = QHBoxLayout()
        self._fav_btn = QPushButton("Favorite")
        self._fav_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._fav_btn.setEnabled(False)
        self._fav_btn.clicked.connect(self._toggle_favorite)
        self._apply_btn = QPushButton("Apply to scene")
        self._apply_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._emit_apply)
        actions.addWidget(self._fav_btn)
        actions.addWidget(self._apply_btn)
        layout.addLayout(actions)

        self._selected: AssetMetadata | None = None
        self._favorites: set[str] = set()
        self._preferred_category: str | None = None
        self._refresh()

    def set_favorites(self, ids: list[str] | set[str]) -> None:
        self._favorites = {str(x) for x in ids}
        self._refresh()

    def set_context_node(self, node_key: str | None) -> None:
        self._preferred_category = _NODE_CATEGORY.get(str(node_key or ""), "") or None
        if self._preferred_category:
            idx = self._category.findData(self._preferred_category)
            if idx >= 0:
                blocked = self._category.blockSignals(True)
                self._category.setCurrentIndex(idx)
                self._category.blockSignals(blocked)
        self._refresh()

    def _refresh(self) -> None:
        query = self._query.text()
        category = self._category.currentData() or None
        mood = self._mood.currentData() or None
        genre = self._genre.currentData() or None
        performance = self._perf.currentData() or None
        results = search_assets(
            query=query,
            category=category or None,
            mood=mood or None,
            genre=genre or None,
            performance=performance or None,
        )
        # Favorites first
        fav = [r for r in results if r.id in self._favorites]
        rest = [r for r in results if r.id not in self._favorites]
        ordered = (*fav, *rest)
        self._list.clear()
        for item in ordered[:200]:
            star = "★ " if item.id in self._favorites else ""
            row = QListWidgetItem(f"{star}{item.name}  ·  {item.category}  ·  {item.performance}")
            row.setData(int(Qt.ItemDataRole.UserRole), item)
            self._list.addItem(row)
        self._selected = None
        self._apply_btn.setEnabled(False)
        self._fav_btn.setEnabled(False)
        self._detail.setText(f"{len(results)} asset(s)")

    def _on_select(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self._selected = None
            self._apply_btn.setEnabled(False)
            self._fav_btn.setEnabled(False)
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
            f"Recommend: {', '.join(meta.recommended) or '—'}\n"
            f"Avoid: {', '.join(meta.avoid) or '—'}\n"
            f"{meta.ai_description}"
        )
        self._apply_btn.setEnabled(meta.category in _APPLY_PATCH_KEYS)
        self._fav_btn.setEnabled(True)
        self._fav_btn.setText("Unfavorite" if meta.id in self._favorites else "Favorite")

    def _toggle_favorite(self) -> None:
        meta = self._selected
        if meta is None:
            return
        is_fav = meta.id not in self._favorites
        self.favorite_toggled.emit(meta.id, is_fav)
        if is_fav:
            self._favorites.add(meta.id)
        else:
            self._favorites.discard(meta.id)
        self._refresh()

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
