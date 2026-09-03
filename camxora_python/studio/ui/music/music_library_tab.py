"""Music library tab — search + playlist template grid."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from studio.ui.inspector_layout import FIELD_GAP, PAGE_TOP, SECTION_GAP
from studio.ui.music.playlist_card import PlaylistTemplateCard
from studio.ui.music.playlist_presets import PLAYLIST_PRESETS, PRESETS_BY_ID, presets_for_category


class _ComingSoonPage(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, PAGE_TOP + 8, 16, 16)
        label = QLabel(f"{title} templates are coming soon.")
        label.setObjectName("EmptyHint")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(label)
        layout.addStretch(1)


class MusicLibraryTab(QWidget):
    playlist_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_id: str | None = PLAYLIST_PRESETS[0].id if PLAYLIST_PRESETS else None
        self._cards: dict[str, PlaylistTemplateCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(12, PAGE_TOP, 12, 12)
        root.setSpacing(SECTION_GAP)

        search_row = QHBoxLayout()
        search_row.setSpacing(FIELD_GAP)
        self._search = QLineEdit()
        self._search.setObjectName("MusicSearchField")
        self._search.setPlaceholderText("Search templates…")
        self._search.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search, 1)
        root.addLayout(search_row)

        self._stack = QStackedWidget(self)
        self._playlist_page = self._build_playlist_page()
        self._stack.addWidget(self._playlist_page)
        for key, label in (
            ("ring", "Ring"),
            ("bars", "Bars"),
            ("wave", "Wave"),
            ("vinyl", "Vinyl"),
            ("lyric", "Lyric"),
        ):
            self._stack.addWidget(_ComingSoonPage(label))
        self._coming_soon_keys = ("ring", "bars", "wave", "vinyl", "lyric")
        root.addWidget(self._stack, 1)

    def _build_playlist_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self._grid = QGridLayout(inner)
        self._grid.setContentsMargins(0, 0, 4, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(12)
        scroll.setWidget(inner)
        self._populate_grid(presets_for_category("playlist"))
        return scroll

    def _populate_grid(self, presets: tuple) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards.clear()
        cols = 2
        for index, preset in enumerate(presets):
            card = PlaylistTemplateCard(preset, selected=preset.id == self._selected_id)
            card.clicked.connect(self._on_card_clicked)
            self._cards[preset.id] = card
            self._grid.addWidget(card, index // cols, index % cols)

    def _on_card_clicked(self, preset_id: str) -> None:
        self._selected_id = preset_id
        for pid, card in self._cards.items():
            card.set_selected(pid == preset_id)
        self.playlist_selected.emit(preset_id)

    def set_category(self, category: str) -> None:
        if category in ("all", "playlist"):
            self._stack.setCurrentWidget(self._playlist_page)
            self._populate_grid(presets_for_category(category))
            self._apply_filter()
        elif category in self._coming_soon_keys:
            idx = 1 + self._coming_soon_keys.index(category)
            self._stack.setCurrentIndex(idx)

    def _apply_filter(self) -> None:
        if self._stack.currentWidget() is not self._playlist_page:
            return
        query = self._search.text().strip().lower()
        visible = 0
        cols = 2
        for preset in presets_for_category("playlist"):
            card = self._cards.get(preset.id)
            if card is None:
                continue
            show = not query or query in preset.name.lower() or query in preset.id
            card.setVisible(show)
            if show:
                self._grid.addWidget(card, visible // cols, visible % cols)
                visible += 1

    def selected_preset_id(self) -> str | None:
        return self._selected_id

    def selected_preset(self):
        if self._selected_id is None:
            return None
        return PRESETS_BY_ID.get(self._selected_id)

    def select_playlist(self, preset_id: str) -> None:
        if preset_id in self._cards:
            self._on_card_clicked(preset_id)
