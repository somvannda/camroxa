"""Music automation card."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from features.create.widgets.icons import apply_button_icon, create_icon, section_heading
from features.create.widgets.studio_controls import StudioCheckBox, StudioComboBox
from features.create.widgets.studio_panel import NestedPanel, StudioPanel
from shared.lib.music_costs import format_plan_credits
from shared.themes.deep_blue import (
    MUSIC_PLAN_SUMMARY_ID,
    MUSIC_PLAN_SUMMARY_TEXT_ID,
    START_BUTTON_ID,
)

_DRAFT = "#A78BFA"
_SUNO = "#38BDF8"
_IMAGE = "#00C878"
_VIDEO = "#14B8A6"
_TOTAL = "#00C878"

AI_STRUCTURE_SENTINEL = "__ai_structure__"
AI_STRUCTURE_LABEL = "AI Structure"
SUNO_STRUCTURE_SENTINEL = "__suno_structure__"
SUNO_STRUCTURE_LABEL = "Suno Structure"
FREE_STRUCTURE_SENTINELS = frozenset({AI_STRUCTURE_SENTINEL, SUNO_STRUCTURE_SENTINEL})
_STRUCTURE_SHUFFLE_TOOLTIP = (
    "When on, songs in the same batch use varied structures from the available Structure list."
)
_STRUCTURE_SHUFFLE_DISABLED_TOOLTIP = (
    "Shuffle applies to Music Structure templates only. "
    "AI Structure and Suno Structure invent their own section layouts."
)


def _transparent(widget: QWidget) -> QWidget:
    widget.setObjectName("TransparentBlock")
    widget.setAutoFillBackground(False)
    return widget


def _icon_tile(name: str, color: str) -> QLabel:
    tile = QLabel()
    tile.setObjectName("TransparentBlock")
    tile.setAutoFillBackground(False)
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setPixmap(create_icon(name, size=14, color=color).pixmap(14, 14))
    return tile


def _dot(color: str) -> QLabel:
    mark = QLabel()
    mark.setFixedSize(8, 8)
    mark.setStyleSheet(f"background-color: {color}; border-radius: 4px; border: none;")
    return mark


def _v_rule() -> QFrame:
    line = QFrame()
    line.setObjectName("PlanColumnRule")
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFixedWidth(1)
    return line


class AutomationCard(StudioPanel):
    generate_requested = Signal()
    automation_changed = Signal()
    description_changed = Signal(str)
    structure_changed = Signal(str)
    mood_changed = Signal(str)
    shuffle_changed = Signal()
    mood_shuffle_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        root.addWidget(section_heading("AUTOMATION", "sparkles"))

        grid = QGridLayout()
        self._description = StudioComboBox()
        self._structure = StudioComboBox()
        self._mood = StudioComboBox()
        for combo in (self._description, self._structure, self._mood):
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        desc_label = QLabel("Description")
        desc_label.setObjectName("FieldLabel")
        grid.addWidget(desc_label, 0, 0)
        grid.addWidget(self._description, 1, 0)

        structure_header = QHBoxLayout()
        structure_header.setContentsMargins(0, 0, 0, 0)
        structure_header.setSpacing(8)
        structure_label = QLabel("Structure")
        structure_label.setObjectName("FieldLabel")
        structure_header.addWidget(structure_label)
        self._shuffle_structure = StudioCheckBox("Shuffle")
        self._shuffle_structure.setToolTip(_STRUCTURE_SHUFFLE_TOOLTIP)
        self._structure.setToolTip(
            "AI Structure: lyric model picks sections (guided). "
            "Suno Structure: native free layout (no section seed). "
            "Templates: fixed Music Structure list."
        )
        structure_header.addWidget(self._shuffle_structure)
        structure_header.addStretch(1)
        grid.addLayout(structure_header, 0, 1)
        grid.addWidget(self._structure, 1, 1)

        mood_header = QHBoxLayout()
        mood_header.setContentsMargins(0, 0, 0, 0)
        mood_header.setSpacing(8)
        mood_label = QLabel("Mood")
        mood_label.setObjectName("FieldLabel")
        mood_header.addWidget(mood_label)
        self._shuffle_mood = StudioCheckBox("Shuffle")
        self._shuffle_mood.setToolTip(
            "When on, songs in the same batch use varied moods from the available Mood list."
        )
        self._mood.setToolTip("Emotional/narrative mood brief used for album, title, and lyric writing.")
        mood_header.addWidget(self._shuffle_mood)
        mood_header.addStretch(1)
        grid.addLayout(mood_header, 0, 2)
        grid.addWidget(self._mood, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        root.addLayout(grid)

        toggles = QGridLayout()
        toggles.setHorizontalSpacing(12)
        toggles.setVerticalSpacing(8)
        self._auto_image = StudioCheckBox("Auto-Gen Image")
        self._auto_gsuno = StudioCheckBox("Auto-GSuno")
        self._auto_image.setToolTip(
            "When off, use History right-click → Image after drafts/Suno complete."
        )
        self._auto_gsuno.setToolTip(
            "When off, use History right-click → Suno after drafts are ready."
        )
        self._auto_video = StudioCheckBox("Auto-Video")
        self._auto_merge = StudioCheckBox("Auto Merge")
        self._auto_reel = StudioCheckBox("Auto Reel")
        self._auto_upload = StudioCheckBox("Auto-Upload")
        self._auto_upload.setEnabled(False)
        self._auto_upload_enabled = False
        for index, checkbox in enumerate(
            (self._auto_image, self._auto_gsuno, self._auto_video, self._auto_merge, self._auto_reel, self._auto_upload)
        ):
            toggles.addWidget(checkbox, index // 2, index % 2)
        root.addLayout(toggles)

        self._generate_label = "Generate"
        self._generate_enabled = False
        self._generating = False
        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setObjectName(START_BUTTON_ID)
        apply_button_icon(self._generate_btn, "sparkles", color="#FFFFFF")
        self._generate_btn.clicked.connect(self.generate_requested.emit)
        root.addWidget(self._generate_btn)

        self._costs_host = _transparent(QWidget())
        costs_row = QHBoxLayout(self._costs_host)
        costs_row.setContentsMargins(0, 0, 0, 0)
        costs_row.setSpacing(10)
        self._unit_draft = QLabel("")
        self._unit_suno = QLabel("")
        self._unit_image = QLabel("")
        for color, label in (
            (_DRAFT, self._unit_draft),
            (_SUNO, self._unit_suno),
            (_IMAGE, self._unit_image),
        ):
            label.setObjectName("PageSubtitle")
            chip = _transparent(QWidget())
            chip_row = QHBoxLayout(chip)
            chip_row.setContentsMargins(0, 0, 0, 0)
            chip_row.setSpacing(6)
            chip_row.addWidget(_dot(color), alignment=Qt.AlignmentFlag.AlignVCenter)
            chip_row.addWidget(label)
            costs_row.addWidget(chip)
        costs_row.addStretch(1)
        root.addWidget(self._costs_host)

        self._plan_box = NestedPanel()
        self._plan_box.setObjectName(MUSIC_PLAN_SUMMARY_ID)
        plan_layout = QVBoxLayout(self._plan_box)
        plan_layout.setContentsMargins(10, 8, 10, 8)
        plan_layout.setSpacing(8)

        self._plan = QLabel("")
        self._plan.setObjectName(MUSIC_PLAN_SUMMARY_TEXT_ID)
        self._plan.setWordWrap(True)
        plan_layout.addWidget(self._plan)

        self._plan_metrics = _transparent(QWidget())
        metrics = QVBoxLayout(self._plan_metrics)
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(8)

        self._batch_value = QLabel("")
        self._batch_caption = QLabel("Total")
        self._song_value = QLabel("")
        self._song_caption = QLabel("Generated")
        self._image_value = QLabel("")
        self._image_caption = QLabel("")
        self._video_value = QLabel("Video / Merge")
        self._video_caption = QLabel("Later")
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        for icon, color, value, caption in (
            ("layers", _DRAFT, self._batch_value, self._batch_caption),
            ("music-4", _SUNO, self._song_value, self._song_caption),
            ("image", _IMAGE, self._image_value, self._image_caption),
            ("video", _VIDEO, self._video_value, self._video_caption),
        ):
            value.setObjectName("PlanMetricValue")
            value.setWordWrap(True)
            caption.setObjectName("FieldLabel")
            caption.setWordWrap(True)
            cell = _transparent(QWidget())
            cell_row = QHBoxLayout(cell)
            cell_row.setContentsMargins(0, 0, 0, 0)
            cell_row.setSpacing(6)
            cell_row.addWidget(_icon_tile(icon, color), alignment=Qt.AlignmentFlag.AlignTop)
            copy = QVBoxLayout()
            copy.setContentsMargins(0, 0, 0, 0)
            copy.setSpacing(0)
            copy.addWidget(value)
            copy.addWidget(caption)
            cell_row.addLayout(copy, stretch=1)
            if top.count():
                top.addWidget(_v_rule())
            top.addWidget(cell, stretch=1)
        metrics.addLayout(top)

        divider = QFrame()
        divider.setObjectName("PlanDashRule")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        metrics.addWidget(divider)

        self._total_credits = QLabel("")
        self._draft_credits = QLabel("")
        self._suno_credits = QLabel("")
        self._image_credits = QLabel("")
        self._video_credits = QLabel("Later")
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(6)
        for color, caption, value, object_name, use_icon in (
            (_TOTAL, "Total credits", self._total_credits, "PlanCreditTotal", True),
            (_DRAFT, "Draft", self._draft_credits, "PlanCreditDraft", False),
            (_SUNO, "Suno", self._suno_credits, "PlanCreditSuno", False),
            (_IMAGE, "Image", self._image_credits, "PlanCreditImage", False),
            (_VIDEO, "Video/Merge", self._video_credits, "PlanCreditVideo", False),
        ):
            value.setObjectName(object_name)
            caption_label = QLabel(caption)
            caption_label.setObjectName("FieldLabel")
            cell = _transparent(QWidget())
            cell_row = QHBoxLayout(cell)
            cell_row.setContentsMargins(0, 0, 0, 0)
            cell_row.setSpacing(4)
            if use_icon:
                cell_row.addWidget(_icon_tile("layers", color), alignment=Qt.AlignmentFlag.AlignTop)
            else:
                cell_row.addWidget(_dot(color), alignment=Qt.AlignmentFlag.AlignTop)
            copy = QVBoxLayout()
            copy.setContentsMargins(0, 0, 0, 0)
            copy.setSpacing(2)
            copy.addWidget(caption_label)
            copy.addWidget(value)
            cell_row.addLayout(copy, stretch=1)
            if bottom.count():
                bottom.addWidget(_v_rule())
            bottom.addWidget(cell, stretch=1)
        metrics.addLayout(bottom)
        self._plan_metrics.hide()
        plan_layout.addWidget(self._plan_metrics)
        root.addWidget(self._plan_box)

        self._helper = QLabel("")
        self._helper.setObjectName("PageSubtitle")
        self._helper.setWordWrap(True)
        self._helper.hide()
        root.addWidget(self._helper)

        self._warning = QLabel("")
        self._warning.setObjectName("music_warning_text")
        self._warning.setWordWrap(True)
        root.addWidget(self._warning)

        self._description.currentIndexChanged.connect(lambda *_: self._emit_description())
        self._structure.currentIndexChanged.connect(lambda *_: self._emit_structure())
        self._mood.currentIndexChanged.connect(lambda *_: self._emit_mood())
        self._shuffle_structure.stateChanged.connect(lambda *_: self.shuffle_changed.emit())
        self._shuffle_mood.stateChanged.connect(lambda *_: self.mood_shuffle_changed.emit())
        for checkbox in (self._auto_image, self._auto_gsuno, self._auto_video, self._auto_merge, self._auto_reel, self._auto_upload):
            checkbox.stateChanged.connect(lambda *_: self.automation_changed.emit())

    def _emit_description(self) -> None:
        self.description_changed.emit(self._description.currentData() or "")

    def _emit_structure(self) -> None:
        self._sync_structure_shuffle_enabled()
        self.structure_changed.emit(self._structure.currentData() or "")

    def _sync_structure_shuffle_enabled(self) -> None:
        free_selected = self.is_free_structure_selected()
        self._shuffle_structure.setEnabled(not free_selected)
        self._shuffle_structure.setToolTip(
            _STRUCTURE_SHUFFLE_DISABLED_TOOLTIP if free_selected else _STRUCTURE_SHUFFLE_TOOLTIP
        )
        if free_selected and self._shuffle_structure.isChecked():
            self._shuffle_structure.blockSignals(True)
            self._shuffle_structure.setChecked(False)
            self._shuffle_structure.blockSignals(False)

    def _emit_mood(self) -> None:
        self.mood_changed.emit(self._mood.currentData() or "")

    def set_options(
        self,
        descriptions: list[tuple[str, str]],
        structures: list[tuple[str, str]],
        moods: list[tuple[str, str]] | None = None,
    ) -> None:
        for combo in (self._description, self._structure, self._mood):
            combo.blockSignals(True)
        try:
            self._description.clear()
            for option_id, name in descriptions:
                self._description.addItem(name, option_id)
            self._structure.clear()
            self._structure.addItem(AI_STRUCTURE_LABEL, AI_STRUCTURE_SENTINEL)
            self._structure.addItem(SUNO_STRUCTURE_LABEL, SUNO_STRUCTURE_SENTINEL)
            for option_id, name in structures:
                self._structure.addItem(name, option_id)
            self._mood.clear()
            for option_id, name in moods or []:
                self._mood.addItem(name, option_id)
        finally:
            for combo in (self._description, self._structure, self._mood):
                combo.blockSignals(False)
                combo.sync_item_tooltips()
        # Do not emit selection changes here — callers apply preferred ids via set_selected_options.
        self._sync_structure_shuffle_enabled()

    def set_selected_options(
        self,
        description_id: str,
        structure_id: str,
        mood_id: str = "",
    ) -> None:
        for combo in (self._description, self._structure, self._mood):
            combo.blockSignals(True)
        try:
            desc_index = self._description.findData(description_id)
            if desc_index >= 0:
                self._description.setCurrentIndex(desc_index)
            if structure_id in FREE_STRUCTURE_SENTINELS:
                lookup_id = structure_id
            elif not structure_id:
                lookup_id = AI_STRUCTURE_SENTINEL
            else:
                lookup_id = structure_id
            struct_index = self._structure.findData(lookup_id)
            if struct_index >= 0:
                self._structure.setCurrentIndex(struct_index)
            if mood_id:
                mood_index = self._mood.findData(mood_id)
                if mood_index >= 0:
                    self._mood.setCurrentIndex(mood_index)
            elif self._mood.count() > 0:
                self._mood.setCurrentIndex(0)
        finally:
            for combo in (self._description, self._structure, self._mood):
                combo.blockSignals(False)
        self._sync_structure_shuffle_enabled()

    def selected_description_id(self) -> str:
        return str(self._description.currentData() or "")

    def selected_structure_id(self) -> str:
        value = str(self._structure.currentData() or "")
        if value in FREE_STRUCTURE_SENTINELS:
            return ""
        return value

    def selected_mood_id(self) -> str:
        return str(self._mood.currentData() or "")

    def is_ai_structure_selected(self) -> bool:
        return str(self._structure.currentData() or "") == AI_STRUCTURE_SENTINEL

    def is_suno_structure_selected(self) -> bool:
        return str(self._structure.currentData() or "") == SUNO_STRUCTURE_SENTINEL

    def is_free_structure_selected(self) -> bool:
        return str(self._structure.currentData() or "") in FREE_STRUCTURE_SENTINELS

    def selected_structure_mode(self) -> str:
        if self.is_ai_structure_selected():
            return "ai_free"
        if self.is_suno_structure_selected():
            return "suno"
        return "template"

    def selected_description_name(self) -> str:
        return self._description.currentText()

    def selected_structure_name(self) -> str:
        return self._structure.currentText()

    def selected_mood_name(self) -> str:
        return self._mood.currentText()

    def shuffle_structure(self) -> bool:
        if self.is_free_structure_selected():
            return False
        return self._shuffle_structure.isChecked()

    def set_shuffle_structure(self, enabled: bool) -> None:
        # Settings restore must not re-check Shuffle while AI/Suno Structure is selected.
        checked = bool(enabled) and not self.is_free_structure_selected()
        self._shuffle_structure.blockSignals(True)
        self._shuffle_structure.setChecked(checked)
        self._shuffle_structure.blockSignals(False)
        self._sync_structure_shuffle_enabled()

    def shuffle_mood(self) -> bool:
        return self._shuffle_mood.isChecked()

    def set_shuffle_mood(self, enabled: bool) -> None:
        self._shuffle_mood.blockSignals(True)
        self._shuffle_mood.setChecked(enabled)
        self._shuffle_mood.blockSignals(False)

    def apply_automation_flags(
        self,
        *,
        auto_gen_image: bool,
        auto_gsuno: bool,
        auto_video_after_suno: bool,
        auto_merge_after_video: bool,
        auto_reel_after_video: bool,
        auto_upload_youtube: bool = False,
    ) -> None:
        self._auto_image.setChecked(auto_gen_image)
        self._auto_gsuno.setChecked(auto_gsuno)
        self._auto_video.setChecked(auto_video_after_suno)
        self._auto_merge.setChecked(auto_merge_after_video)
        self._auto_reel.setChecked(auto_reel_after_video)
        if self._auto_upload_enabled:
            self._auto_upload.setChecked(auto_upload_youtube)

    def set_auto_upload_enabled(self, enabled: bool) -> None:
        self._auto_upload_enabled = enabled
        self._auto_upload.setEnabled(enabled)
        if not enabled:
            self._auto_upload.setChecked(False)

    def automation_values(self) -> dict[str, bool]:
        return {
            "auto_gen_image": self._auto_image.isChecked(),
            "auto_gsuno": self._auto_gsuno.isChecked(),
            "auto_video_after_suno": self._auto_video.isChecked(),
            "auto_merge_after_video": self._auto_merge.isChecked(),
            "auto_reel_after_video": self._auto_reel.isChecked(),
            "auto_upload_youtube": self._auto_upload.isChecked() if self._auto_upload_enabled else False,
        }

    def set_cost_lines(self, text: str) -> None:
        parts = [part.strip() for part in str(text or "").split("·") if part.strip()]
        self._unit_draft.setText(parts[0] if len(parts) > 0 else "")
        self._unit_suno.setText(parts[1] if len(parts) > 1 else "")
        self._unit_image.setText(parts[2] if len(parts) > 2 else "")
        self._costs_host.setVisible(bool(parts))

    def set_plan_lines(self, text: str) -> None:
        cleaned = str(text or "").strip()
        self._plan.setText(cleaned)
        self._plan.setVisible(bool(cleaned))
        self._plan_metrics.hide()
        self._plan_box.setVisible(bool(cleaned))

    def set_plan_summary(
        self,
        *,
        batches: int,
        songs: int,
        image_jobs: int,
        draft_credits: float | None,
        suno_credits: float | None,
        image_credits: float | None,
        total_credits: float | None,
        video_later: bool,
    ) -> None:
        batch_label = "batch" if batches == 1 else "batches"
        self._batch_value.setText(f"{batches} {batch_label}")
        song_label = "song" if songs == 1 else "songs"
        self._song_value.setText(f"{songs} {song_label}")
        self._image_value.setText(f"Image {image_jobs}")
        self._image_caption.setText(f"({image_jobs} jobs)")
        self._video_caption.setText("Later" if video_later else "Off")
        self._video_credits.setText("Later" if video_later else "Off")
        self._total_credits.setText(format_plan_credits(total_credits))
        self._draft_credits.setText(format_plan_credits(draft_credits))
        self._suno_credits.setText(format_plan_credits(suno_credits))
        self._image_credits.setText(format_plan_credits(image_credits))
        self._plan.clear()
        self._plan.hide()
        self._plan_metrics.show()
        self._plan_box.show()

    def set_helper_text(self, text: str) -> None:
        cleaned = str(text or "").strip()
        self._helper.setText(cleaned)
        self._helper.setVisible(bool(cleaned))

    def set_warning_text(self, text: str) -> None:
        cleaned = str(text or "").strip()
        self._warning.setText(cleaned)
        self._warning.setVisible(bool(cleaned))

    def set_generate_label(self, text: str) -> None:
        self._generate_label = text
        if not self._generating:
            self._generate_btn.setText(text)

    def set_generate_enabled(self, enabled: bool) -> None:
        self._generate_enabled = enabled
        self._apply_generate_button_state()

    def set_generating(self, generating: bool) -> None:
        self._generating = generating
        if generating:
            self._generate_btn.setText("Generating...")
        elif self._generate_label:
            self._generate_btn.setText(self._generate_label)
        self._apply_generate_button_state()

    def _apply_generate_button_state(self) -> None:
        self._generate_btn.setEnabled(self._generate_enabled and not self._generating)
