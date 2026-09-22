"""Sub-template grid for the Playlist Templates tab."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from studio.core.playlist_settings import PlaylistSettings
from studio.core.playlist_style import apply_style_to_settings
from studio.core.playlist_sub_template_styles import switch_sub_template
from studio.core.playlist_sub_templates import PLAYLIST_SUB_TEMPLATES, SUB_TEMPLATES_BY_ID
from studio.ui.inspector_layout import FIELD_GAP
from studio.ui.music.playlist_sub_template_card import PlaylistSubTemplateCard


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


class PlaylistStylePicker(QWidget):
    """10 track-list sub-template cards."""

    style_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = PlaylistSettings()
        self._sub_cards: dict[str, PlaylistSubTemplateCard] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_field_label("Track list style"))
        layout.addSpacing(FIELD_GAP)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        cols = 2
        for index, sub in enumerate(PLAYLIST_SUB_TEMPLATES):
            card = PlaylistSubTemplateCard(sub, selected=sub.id == self._settings.sub_template_id)
            card.clicked.connect(self._on_sub_clicked)
            self._sub_cards[sub.id] = card
            grid.addWidget(card, index // cols, index % cols)
        layout.addLayout(grid)

    def load_settings(self, settings: PlaylistSettings) -> None:
        self._settings = settings
        sub_id = settings.sub_template_id or "glass-blur"
        for sid, card in self._sub_cards.items():
            card.set_selected(sid == sub_id)

    def settings(self) -> PlaylistSettings:
        return self._settings

    def _on_sub_clicked(self, sub_id: str) -> None:
        if sub_id not in SUB_TEMPLATES_BY_ID:
            return
        switch_sub_template(self._settings, sub_id)
        apply_style_to_settings(self._settings)
        self.load_settings(self._settings)
        self.style_changed.emit()
