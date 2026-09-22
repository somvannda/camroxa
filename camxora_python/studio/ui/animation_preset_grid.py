"""CapCut-style animation preset grid with icon/GIF hover previews."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from studio.app.selection_style import animation_card_style
from studio.ui.animation_presets import PRESETS_BY_CATEGORY, AnimationPresetInfo, animation_preview_path
from studio.ui.clip_inspector_tabs import InspectorTabRow
from studio.ui.icons.lucide_icons import ICON_SZ_ANIMATION, lucide_pixmap


class AnimationPresetCard(QFrame):
    clicked = Signal(str)

    def __init__(
        self,
        preset: AnimationPresetInfo,
        *,
        selected: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preset = preset
        self.preset_id = preset.id
        self.setObjectName("AnimationPresetCard")
        self.setProperty("selected", "true" if selected else "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(92, 96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 4)
        layout.setSpacing(4)

        self._preview = QLabel(self)
        self._preview.setObjectName("AnimationPresetPreview")
        self._preview.setFixedSize(80, 56)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_static_preview()
        layout.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._name_label = QLabel(preset.name)
        self._name_label.setObjectName("AnimationPresetName")
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._name_label.setWordWrap(True)
        layout.addWidget(self._name_label)

        self._apply_selection(selected)

        self._movie: QMovie | None = None
        gif_path = animation_preview_path(preset.id)
        if gif_path is not None:
            self._movie = QMovie(str(gif_path))
            self._movie.setScaledSize(self._preview.size())
            self.setToolTip(f"{preset.name} — hover to preview")
        else:
            self.setToolTip(preset.name)

    def _apply_selection(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        frame_qss, name_qss = animation_card_style(selected=selected)
        self.setStyleSheet(frame_qss)
        self._name_label.setStyleSheet(name_qss)

    def _apply_static_preview(self) -> None:
        self._preview.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f" stop:0 {self._preset.swatch_from}, stop:1 {self._preset.swatch_to});"
            f" border-radius: 8px;"
        )
        self._preview.setPixmap(
            lucide_pixmap(self._preset.icon, size=ICON_SZ_ANIMATION, color="#ffffff")
        )

    def enterEvent(self, event) -> None:  # noqa: N802
        if self._movie is not None:
            self._preview.setStyleSheet("background: #0a0a0f; border-radius: 8px;")
            self._preview.setPixmap(QPixmap())
            self._preview.setMovie(self._movie)
            self._movie.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._movie is not None:
            self._movie.stop()
            self._preview.setMovie(None)
            self._apply_static_preview()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.preset_id)
        super().mousePressEvent(event)


class AnimationPresetGrid(QWidget):
    """Animation presets — In / Out / Combo (+ Audio for image clips)."""

    preset_selected = Signal(str, str)  # category, preset_id

    def __init__(
        self,
        *,
        for_image: bool = False,
        initial_tab: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._for_image = for_image
        self._categories = ("in", "out", "combo", "audio") if for_image else ("in", "out", "combo")
        tab_labels = ("In", "Out", "Combo", "Audio") if for_image else ("In", "Out", "Combo")
        self._selected: dict[str, str] = {cat: "none" for cat in self._categories}

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(8)
        self._tier2 = InspectorTabRow(tab_labels, self)
        if for_image:
            self._tier2.set_tab_tooltip("Audio", "Audio reactivity — animate to music on the timeline")
        self._tier2.tab_changed.connect(self._show_category)
        self._outer.addWidget(self._tier2)
        self._grid_host = QWidget(self)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(6)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._outer.addWidget(self._grid_host)
        self._hint = QLabel("")
        self._hint.setObjectName("EmptyHint")
        self._hint.setWordWrap(True)
        self._outer.addWidget(self._hint)
        self._outer.addStretch(1)

        start = max(0, min(initial_tab, len(self._categories) - 1))
        self._tier2.set_active_index(start)
        self._show_category(start)

    def active_tab_index(self) -> int:
        return self._tier2.active_index()

    def _show_category(self, index: int) -> None:
        key = self._categories[index]
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        presets = PRESETS_BY_CATEGORY.get(key, ())
        for i, preset in enumerate(presets):
            card = AnimationPresetCard(preset, selected=self._selected.get(key) == preset.id)
            card.clicked.connect(lambda pid, cat=key: self._on_pick(cat, pid))
            self._grid.addWidget(card, i // 3, i % 3)
        if key == "audio":
            self._hint.setText(
                "Audio reactivity uses timeline audio — playback wiring coming soon. "
                "Add GIF loops under assets/animations/ for hover previews."
            )
        else:
            self._hint.setText(
                "Hover a preset to preview (GIF when bundled). "
                "Add assets/animations/{preset-id}.gif for CapCut-style loops."
            )

    def _on_pick(self, category: str, preset_id: str) -> None:
        self._selected[category] = preset_id
        self.preset_selected.emit(category, preset_id)
        self._show_category(self._categories.index(category))
