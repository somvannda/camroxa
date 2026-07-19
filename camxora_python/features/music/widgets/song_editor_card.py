"""Music song editor card."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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

from features.music.widgets.lyrics_suno_highlighter import (
    apply_lyrics_suno_highlights,
    clear_lyrics_suno_highlights,
)
from shared.lib.suno_lyrics_sanitize import (
    SunoPlatformBlocklist,
    SunoSanitizeReplacement,
    find_suno_risk_terms_in_text,
    format_suno_replacements,
    sanitize_text_for_suno_with_changes,
)
from shared.themes.deep_blue import SHELL_TEXT_EDIT_ID, SUBTITLE_LABEL_ID

_SUNO_SCAN_DEBOUNCE_MS = 400


class SongEditorCard(QFrame):
    draft_requested = Signal()
    polish_requested = Signal()
    copy_title_requested = Signal()
    copy_lyrics_requested = Signal()
    copy_both_requested = Signal()
    field_changed = Signal()
    suno_auto_fixed = Signal(str)

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
        self._draft_btn.clicked.connect(self.draft_requested.emit)
        self._draft_btn.hide()
        header.addWidget(self._draft_btn)
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

        self._polish_slider = QSlider()
        self._polish_slider.setOrientation(Qt.Orientation.Horizontal)
        self._polish_slider.setRange(0, 100)
        self._polish_slider.setValue(85)
        self._polish_value = QLabel("85")
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

        suno_banner_row = QHBoxLayout()
        self._suno_risk_banner = QLabel("")
        self._suno_risk_banner.setObjectName(SUBTITLE_LABEL_ID)
        self._suno_risk_banner.setWordWrap(True)
        self._suno_risk_banner.hide()
        suno_banner_row.addWidget(self._suno_risk_banner, stretch=1)
        self._suno_auto_fix_btn = QPushButton("Auto-fix")
        self._suno_auto_fix_btn.clicked.connect(self._apply_suno_auto_fix)
        self._suno_auto_fix_btn.hide()
        suno_banner_row.addWidget(self._suno_auto_fix_btn)
        root.addLayout(suno_banner_row)

        actions = QHBoxLayout()
        for label, slot in (
            ("Copy title", self.copy_title_requested),
            ("Copy lyrics", self.copy_lyrics_requested),
            ("Copy both", self.copy_both_requested),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot.emit)
            actions.addWidget(button)
        self._polish_btn = QPushButton("Rewrite lyrics")
        self._polish_btn.clicked.connect(self.polish_requested.emit)
        actions.addWidget(self._polish_btn)
        revisions = QPushButton("Revisions (0 Credits)")
        revisions.setEnabled(False)
        revisions.hide()
        actions.addStretch()
        root.addLayout(actions)

        self._lyrics = QTextEdit()
        self._lyrics.setObjectName(SHELL_TEXT_EDIT_ID)
        self._lyrics.setPlaceholderText("Lyrics")
        self._lyrics.setMinimumHeight(180)
        root.addWidget(self._lyrics, stretch=1)

        self._learned_suno_terms: list[str] = []
        self._platform_blocklist: SunoPlatformBlocklist | None = None
        self._suno_scan_timer = QTimer(self)
        self._suno_scan_timer.setSingleShot(True)
        self._suno_scan_timer.setInterval(_SUNO_SCAN_DEBOUNCE_MS)
        self._suno_scan_timer.timeout.connect(self._run_suno_scan)

        self._title.textChanged.connect(self._on_title_changed)
        self._album.textChanged.connect(lambda *_: self.field_changed.emit())
        self._lyrics.textChanged.connect(self._on_lyrics_changed)
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

    def _on_title_changed(self) -> None:
        self.field_changed.emit()
        self._suno_scan_timer.start()

    def _on_lyrics_changed(self) -> None:
        self.field_changed.emit()
        self._suno_scan_timer.start()

    def set_learned_suno_terms(self, terms: list[str] | None) -> None:
        self._learned_suno_terms = [str(term).strip().lower() for term in (terms or []) if str(term).strip()]
        self._run_suno_scan()

    def set_platform_suno_blocklist(
        self,
        *,
        replacements: dict[str, str] | None = None,
        block_terms: list[str] | None = None,
        warn_terms: list[str] | None = None,
    ) -> None:
        if not replacements and not block_terms and not warn_terms:
            self._platform_blocklist = None
        else:
            self._platform_blocklist = SunoPlatformBlocklist(
                replacements={
                    str(key).strip().lower(): str(value).strip()
                    for key, value in (replacements or {}).items()
                    if str(key).strip() and str(value).strip()
                },
                block_terms=frozenset(
                    str(term).strip().lower() for term in (block_terms or []) if str(term).strip()
                ),
                warn_terms=frozenset(
                    str(term).strip().lower() for term in (warn_terms or []) if str(term).strip()
                ),
            )
        self._run_suno_scan()

    def _collect_suno_hits(self) -> tuple[list, list]:
        title_hits: list = []
        lyrics_hits: list = []
        title = self._title.text().strip()
        lyrics = self._lyrics.toPlainText()
        if title:
            title_hits = find_suno_risk_terms_in_text(
                title,
                learned_terms=self._learned_suno_terms,
                platform_blocklist=self._platform_blocklist,
            )
        if lyrics.strip():
            lyrics_hits = find_suno_risk_terms_in_text(
                lyrics,
                learned_terms=self._learned_suno_terms,
                platform_blocklist=self._platform_blocklist,
            )
        return title_hits, lyrics_hits

    def _run_suno_scan(self) -> None:
        lyrics = self._lyrics.toPlainText()
        if not lyrics.strip() and not self._title.text().strip():
            clear_lyrics_suno_highlights(self._lyrics)
            self._suno_risk_banner.hide()
            self._suno_auto_fix_btn.hide()
            return

        title_hits, lyrics_hits = self._collect_suno_hits()
        hits = title_hits + lyrics_hits
        apply_lyrics_suno_highlights(self._lyrics, lyrics_hits)
        block_count = sum(1 for hit in hits if hit.severity == "block")
        warn_count = sum(1 for hit in hits if hit.severity == "warn")
        if block_count or warn_count:
            parts: list[str] = []
            if block_count:
                parts.append(f"{block_count} blocked term{'s' if block_count != 1 else ''}")
            if warn_count:
                parts.append(f"{warn_count} risky pattern{'s' if warn_count != 1 else ''}")
            banner_parts = ["Suno check: " + ", ".join(parts) + ". Hover highlights for suggestions."]
            title_blocks = [hit.term for hit in title_hits if hit.severity == "block"]
            if title_blocks:
                banner_parts.append(f"Title flagged: {', '.join(title_blocks[:3])}.")
            self._suno_risk_banner.setText(" ".join(banner_parts))
            self._suno_risk_banner.show()
            self._suno_auto_fix_btn.setVisible(block_count > 0)
        else:
            self._suno_risk_banner.hide()
            self._suno_auto_fix_btn.hide()

    def _apply_suno_auto_fix(self) -> None:
        replacements: list[SunoSanitizeReplacement] = []
        title_text = self._title.text()
        lyrics_text = self._lyrics.toPlainText()

        cleaned_title, title_changes = sanitize_text_for_suno_with_changes(
            title_text,
            field="title",
            blocked_terms=self._learned_suno_terms,
            platform_blocklist=self._platform_blocklist,
        )
        cleaned_lyrics, lyrics_changes = sanitize_text_for_suno_with_changes(
            lyrics_text,
            field="lyrics",
            blocked_terms=self._learned_suno_terms,
            platform_blocklist=self._platform_blocklist,
        )
        replacements.extend(title_changes)
        replacements.extend(lyrics_changes)

        if cleaned_title != title_text:
            self._title.setText(cleaned_title)
        if cleaned_lyrics != lyrics_text:
            self._lyrics.setPlainText(cleaned_lyrics)

        self._run_suno_scan()
        self.field_changed.emit()

        summary = format_suno_replacements(replacements)
        if summary:
            self.suno_auto_fixed.emit(summary)

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
        self._run_suno_scan()

    def set_draft_enabled(self, enabled: bool) -> None:
        self._draft_btn.setEnabled(enabled)

    def set_polish_enabled(self, enabled: bool, *, reason: str = "") -> None:
        self._polish_btn.setEnabled(enabled)
        self._polish_btn.setToolTip(reason if reason and not enabled else "")
