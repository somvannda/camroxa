"""Music song editor card."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shared.themes.deep_blue import SHELL_TEXT_EDIT_ID, SUBTITLE_LABEL_ID


class SongEditorCard(QFrame):
    draft_requested = Signal()
    polish_requested = Signal()
    copy_title_requested = Signal()
    copy_lyrics_requested = Signal()
    copy_both_requested = Signal()
    field_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("SONG")
        title.setObjectName(SUBTITLE_LABEL_ID)
        header.addWidget(title)
        header.addStretch()
        self._draft_btn = QPushButton("Draft")
        self._polish_btn = QPushButton("Polish")
        self._draft_btn.clicked.connect(self.draft_requested.emit)
        self._polish_btn.clicked.connect(self.polish_requested.emit)
        self._draft_btn.hide()
        self._polish_btn.hide()
        header.addWidget(self._draft_btn)
        header.addWidget(self._polish_btn)
        root.addLayout(header)

        effects = QGridLayout()
        self._valence = self._make_effect_slider()
        self._dance = self._make_effect_slider()
        self._instrumental = self._make_effect_slider()
        self._valence_value = QLabel("0")
        self._dance_value = QLabel("0")
        self._instrumental_value = QLabel("0")
        for col, (label, slider, value_label) in enumerate(
            (
                ("Valence", self._valence, self._valence_value),
                ("Danceability", self._dance, self._dance_value),
                ("Instrumental", self._instrumental, self._instrumental_value),
            )
        ):
            effects.addWidget(QLabel(label), 0, col)
            row = QHBoxLayout()
            row.addWidget(slider, stretch=1)
            row.addWidget(value_label)
            host = QWidget()
            host.setLayout(row)
            effects.addWidget(host, 1, col)

        # Polish UI hidden for launch (API also rejects polish).
        self._polish_slider = QSlider()
        self._polish_slider.setOrientation(Qt.Orientation.Horizontal)
        self._polish_slider.setRange(0, 100)
        self._polish_slider.setValue(60)
        self._polish_value = QLabel("60")
        self._polish_slider.hide()
        self._polish_value.hide()
        root.addLayout(effects)

        fields = QHBoxLayout()
        self._title = QLineEdit()
        self._title.setPlaceholderText("Song title")
        self._album = QLineEdit()
        self._album.setPlaceholderText("album 1")
        fields.addWidget(self._title, stretch=3)
        fields.addWidget(self._album, stretch=2)
        root.addLayout(fields)

        self._seed_notice = QLabel("")
        self._seed_notice.setObjectName(SUBTITLE_LABEL_ID)
        self._seed_notice.setWordWrap(True)
        self._seed_notice.hide()
        root.addWidget(self._seed_notice)

        actions = QHBoxLayout()
        for label, slot in (
            ("Copy title", self.copy_title_requested),
            ("Copy lyrics", self.copy_lyrics_requested),
            ("Copy both", self.copy_both_requested),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot.emit)
            actions.addWidget(button)
        self._polish_again_btn = QPushButton("Polish")
        self._polish_again_btn.clicked.connect(self.polish_requested.emit)
        self._polish_again_btn.hide()
        revisions = QPushButton("Revisions (0 Credits)")
        revisions.setEnabled(False)
        revisions.hide()
        root.addLayout(actions)

        self._lyrics = QTextEdit()
        self._lyrics.setObjectName(SHELL_TEXT_EDIT_ID)
        self._lyrics.setPlaceholderText("Lyrics")
        self._lyrics.setMinimumHeight(180)
        root.addWidget(self._lyrics, stretch=1)

        self._title.textChanged.connect(lambda *_: self.field_changed.emit())
        self._album.textChanged.connect(lambda *_: self.field_changed.emit())
        self._lyrics.textChanged.connect(lambda *_: self.field_changed.emit())
        self._polish_slider.valueChanged.connect(self._on_polish_changed)

    @staticmethod
    def _make_effect_slider() -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setEnabled(False)
        return slider

    def _on_polish_changed(self, value: int) -> None:
        self._polish_value.setText(str(value))
        self.field_changed.emit()

    def set_effect_values(self, valence: int, danceability: int, instrumentalness: int) -> None:
        self._valence.setValue(valence)
        self._dance.setValue(danceability)
        self._instrumental.setValue(instrumentalness)
        self._valence_value.setText(str(valence))
        self._dance_value.setText(str(danceability))
        self._instrumental_value.setText(str(instrumentalness))

    def set_button_labels(self, draft: str, polish: str) -> None:
        self._draft_btn.setText(draft)
        self._polish_btn.setText(polish)

    def set_seed_notice(self, text: str) -> None:
        if text:
            self._seed_notice.setText(text)
            self._seed_notice.show()
        else:
            self._seed_notice.hide()

    def set_pending(self, *, draft: bool, polish: bool) -> None:
        self._draft_btn.setEnabled(not draft and bool(self._title.text() or True))
        self._polish_btn.setEnabled(not polish and bool(self._lyrics.toPlainText().strip()))

    def title(self) -> str:
        return self._title.text()

    def album(self) -> str:
        return self._album.text()

    def lyrics(self) -> str:
        return self._lyrics.toPlainText()

    def polish_strength(self) -> int:
        return self._polish_slider.value()

    def set_fields(self, *, title: str, album: str, lyrics: str, polish_strength: int) -> None:
        self._title.setText(title)
        self._album.setText(album)
        self._lyrics.setPlainText(lyrics)
        self._polish_slider.setValue(polish_strength)

    def set_draft_enabled(self, enabled: bool) -> None:
        self._draft_btn.setEnabled(enabled)

    def set_polish_enabled(self, enabled: bool) -> None:
        del enabled  # polish disabled for launch
        self._polish_btn.setEnabled(False)
        if hasattr(self, "_polish_again_btn"):
            self._polish_again_btn.setEnabled(False)
