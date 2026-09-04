"""Music library tab — Playlist whole-look template chooser.

When the user opens the Playlist section they pick between the two
implemented whole-look templates (Minimal White, Forest Mist). Cards reuse
the original track-list sub-template art (bundled thumbnail when present)
and are laid out side by side in one compact row — no category rail, no
search, no extra padding.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from studio.core.playlist_sub_templates import DEFAULT_SUB_FOR_TEMPLATE, SUB_TEMPLATES_BY_ID
from studio.ui.music.playlist_presets import PRESETS_BY_ID
from studio.ui.music.playlist_sub_template_card import PlaylistSubTemplateCard


# The two whole-look templates offered in the picker. Each is both a main
# template id and its matching track-list sub-template id, so a single card
# click applies the complete look (scene + colors + list style) at once.
PICKER_TEMPLATE_IDS = ("minimal-white", "forest-mist")


def _sub_ids_from_template(template_id: str | None) -> str | None:
    """Map an active template id to the picker sub-template it should light up."""
    if not template_id:
        return None
    if template_id in PICKER_TEMPLATE_IDS:
        return template_id
    default_sub = DEFAULT_SUB_FOR_TEMPLATE.get(template_id)
    if default_sub in PICKER_TEMPLATE_IDS:
        return default_sub
    return None


class MusicLibraryTab(QWidget):
    playlist_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_id: str | None = PICKER_TEMPLATE_IDS[0]
        self._cards: dict[str, PlaylistSubTemplateCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 6, 4, 6)
        root.setSpacing(8)

        # One compact row: Minimal White | Forest Mist.
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for sub_id in PICKER_TEMPLATE_IDS:
            sub = SUB_TEMPLATES_BY_ID[sub_id]
            card = PlaylistSubTemplateCard(sub, selected=sub_id == self._selected_id)
            card.clicked.connect(self._on_card_clicked)
            self._cards[sub_id] = card
            row.addWidget(card)
        root.addLayout(row)
        root.addStretch(1)

    def _on_card_clicked(self, sub_id: str) -> None:
        # sub id == whole-look main template id for both picker entries.
        if sub_id not in PRESETS_BY_ID or sub_id not in self._cards:
            return
        self._selected_id = sub_id
        for pid, card in self._cards.items():
            card.set_selected(pid == sub_id)
        self.playlist_selected.emit(sub_id)

    def set_category(self, category: str) -> None:
        # Category rail removed — picker always shows the two templates.
        return None

    def sync_selection(self, template_id: str | None) -> None:
        """Highlight the card matching the active playlist template.

        Called when the Playlist section opens so a template applied from the
        right panel (or loaded project) is shown as selected.
        """
        sub_id = _sub_ids_from_template(template_id)
        if sub_id is None:
            return
        self._selected_id = sub_id
        for pid, card in self._cards.items():
            card.set_selected(pid == sub_id)

    def select_playlist(self, preset_id: str) -> None:
        """Programmatic selection (from the right-panel playlist picker)."""
        if preset_id not in PRESETS_BY_ID:
            return
        self._selected_id = preset_id
        sub_id = _sub_ids_from_template(preset_id) or preset_id
        for pid, card in self._cards.items():
            card.set_selected(pid == sub_id)
        self.playlist_selected.emit(preset_id)

    def selected_preset_id(self) -> str | None:
        return self._selected_id

    def selected_preset(self):
        if self._selected_id is None:
            return None
        return PRESETS_BY_ID.get(self._selected_id)
