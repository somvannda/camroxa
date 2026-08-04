"""Music automation card."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shared.themes.deep_blue import (
    MUSIC_PLAN_SUMMARY_ID,
    MUSIC_PLAN_SUMMARY_TEXT_ID,
    START_BUTTON_ID,
    SUBTITLE_LABEL_ID,
)

AI_STRUCTURE_SENTINEL = "__ai_structure__"
AI_STRUCTURE_LABEL = "AI Structure"


class AutomationCard(QFrame):
    generate_requested = Signal()
    automation_changed = Signal()
    description_changed = Signal(str)
    structure_changed = Signal(str)
    mood_changed = Signal(str)
    shuffle_changed = Signal()
    mood_shuffle_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel("AUTOMATION")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        grid = QGridLayout()
        self._description = QComboBox()
        self._structure = QComboBox()
        self._mood = QComboBox()
        for combo in (self._description, self._structure, self._mood):
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(QLabel("Description"), 0, 0)
        grid.addWidget(self._description, 1, 0)

        structure_header = QHBoxLayout()
        structure_header.setContentsMargins(0, 0, 0, 0)
        structure_header.setSpacing(8)
        structure_header.addWidget(QLabel("Structure"))
        self._shuffle_structure = QCheckBox("Shuffle")
        self._shuffle_structure.setToolTip(
            "When on, songs in the same batch use varied structures from the available Structure list."
        )
        self._structure.setToolTip(
            "Choose a fixed template, or AI Structure to let the lyric model pick sections."
        )
        structure_header.addWidget(self._shuffle_structure)
        structure_header.addStretch(1)
        grid.addLayout(structure_header, 0, 1)
        grid.addWidget(self._structure, 1, 1)

        mood_header = QHBoxLayout()
        mood_header.setContentsMargins(0, 0, 0, 0)
        mood_header.setSpacing(8)
        mood_header.addWidget(QLabel("Mood"))
        self._shuffle_mood = QCheckBox("Shuffle")
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
        self._auto_image = QCheckBox("Auto-Gen Image (off by default)")
        self._auto_gsuno = QCheckBox("Auto-GSuno (off by default)")
        self._auto_image.setToolTip(
            "When off, use History right-click → Image after drafts/Suno complete."
        )
        self._auto_gsuno.setToolTip(
            "When off, use History right-click → Suno after drafts are ready."
        )
        self._auto_video = QCheckBox("Auto-Video")
        self._auto_merge = QCheckBox("Auto Merge")
        self._auto_reel = QCheckBox("Auto Reel")
        self._auto_upload = QCheckBox("Auto-Upload")
        self._auto_upload.setEnabled(False)
        self._auto_upload_enabled = False
        for index, checkbox in enumerate(
            (self._auto_image, self._auto_gsuno, self._auto_video, self._auto_merge, self._auto_reel, self._auto_upload)
        ):
            toggles.addWidget(checkbox, index // 2, index % 2)
        root.addLayout(toggles)

        self._costs = QLabel("")
        self._costs.setObjectName(SUBTITLE_LABEL_ID)
        self._costs.setWordWrap(True)
        root.addWidget(self._costs)

        self._generate_label = "Generate"
        self._generate_enabled = False
        self._generating = False
        self._generate_btn = QPushButton("Generate")
        self._generate_btn.setObjectName(START_BUTTON_ID)
        self._generate_btn.clicked.connect(self.generate_requested.emit)
        root.addWidget(self._generate_btn)

        self._plan_box = QFrame()
        self._plan_box.setObjectName(MUSIC_PLAN_SUMMARY_ID)
        plan_layout = QVBoxLayout(self._plan_box)
        plan_layout.setContentsMargins(10, 8, 10, 8)
        plan_layout.setSpacing(0)
        self._plan = QLabel("")
        self._plan.setObjectName(MUSIC_PLAN_SUMMARY_TEXT_ID)
        self._plan.setWordWrap(True)
        plan_layout.addWidget(self._plan)
        root.addWidget(self._plan_box)

        self._helper = QLabel("")
        self._helper.setObjectName(SUBTITLE_LABEL_ID)
        self._helper.setWordWrap(True)
        self._helper.hide()
        root.addWidget(self._helper)

        self._warning = QLabel("")
        self._warning.setObjectName(SUBTITLE_LABEL_ID)
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
        ai_selected = self.is_ai_structure_selected()
        self._shuffle_structure.setEnabled(not ai_selected)
        if ai_selected:
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
            for option_id, name in structures:
                self._structure.addItem(name, option_id)
            self._mood.clear()
            for option_id, name in moods or []:
                self._mood.addItem(name, option_id)
        finally:
            for combo in (self._description, self._structure, self._mood):
                combo.blockSignals(False)
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
            lookup_id = AI_STRUCTURE_SENTINEL if not structure_id else structure_id
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
        if value == AI_STRUCTURE_SENTINEL:
            return ""
        return value

    def selected_mood_id(self) -> str:
        return str(self._mood.currentData() or "")

    def is_ai_structure_selected(self) -> bool:
        return str(self._structure.currentData() or "") == AI_STRUCTURE_SENTINEL

    def selected_structure_mode(self) -> str:
        return "ai_free" if self.is_ai_structure_selected() else "template"

    def selected_description_name(self) -> str:
        return self._description.currentText()

    def selected_structure_name(self) -> str:
        return self._structure.currentText()

    def selected_mood_name(self) -> str:
        return self._mood.currentText()

    def shuffle_structure(self) -> bool:
        return self._shuffle_structure.isChecked()

    def set_shuffle_structure(self, enabled: bool) -> None:
        self._shuffle_structure.blockSignals(True)
        self._shuffle_structure.setChecked(enabled)
        self._shuffle_structure.blockSignals(False)

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
        self._costs.setText(text)
        self._costs.setVisible(bool(str(text or "").strip()))

    def set_plan_lines(self, text: str) -> None:
        cleaned = str(text or "").strip()
        self._plan.setText(cleaned)
        self._plan_box.setVisible(bool(cleaned))

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
