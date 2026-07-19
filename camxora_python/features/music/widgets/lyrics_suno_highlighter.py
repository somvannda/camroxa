"""Highlight Suno lyric risk terms inside a QTextEdit."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from shared.lib.suno_lyrics_sanitize import SunoLyricsRiskHit

_BLOCK_BG = QColor(180, 40, 40, 90)
_WARN_BG = QColor(200, 160, 40, 90)


def apply_lyrics_suno_highlights(editor: QTextEdit, hits: list[SunoLyricsRiskHit]) -> None:
    selections = []
    for hit in hits:
        selection = QTextEdit.ExtraSelection()
        fmt = QTextCharFormat()
        fmt.setBackground(_BLOCK_BG if hit.severity == "block" else _WARN_BG)
        fmt.setToolTip(hit.suggestion)
        cursor = editor.textCursor()
        cursor.setPosition(max(0, hit.start))
        cursor.setPosition(max(hit.start, hit.end), QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        selection.format = fmt
        selections.append(selection)
    editor.setExtraSelections(selections)


def clear_lyrics_suno_highlights(editor: QTextEdit) -> None:
    editor.setExtraSelections([])
