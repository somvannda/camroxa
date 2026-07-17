"""Workspace asset summary cards — background, logo, track, run directory."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from shared.themes.deep_blue import SUBTITLE_LABEL_ID


def _file_name(path: str, *, fallback: str = "Not selected") -> str:
    candidate = str(path or "").strip()
    if not candidate:
        return fallback
    return Path(candidate).name or fallback


class _WorkspaceAssetCard(QFrame):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        title = QLabel(label.upper())
        title.setObjectName(SUBTITLE_LABEL_ID)
        layout.addWidget(title)
        self._value = QLabel("Not selected")
        layout.addWidget(self._value)
        self._detail = QLabel("")
        self._detail.setObjectName(SUBTITLE_LABEL_ID)
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

    def bind(self, *, value: str, detail: str, ready: bool) -> None:
        self._value.setText(value or "Not selected")
        self._detail.setText(detail or "")
        tone = "#34d399" if ready else "#fbbf24"
        self._value.setStyleSheet(f"color: {tone};")


class WorkspaceAssetSummary(QWidget):
    """2x2 grid of asset status cards, shown at the top of the right rail."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        cards = QGridLayout(self)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(6)
        cards.setVerticalSpacing(6)
        self._background_card = _WorkspaceAssetCard("Background")
        self._logo_card = _WorkspaceAssetCard("Logo")
        self._track_card = _WorkspaceAssetCard("Track")
        self._run_dir_card = _WorkspaceAssetCard("Run Directory")
        cards.addWidget(self._background_card, 0, 0)
        cards.addWidget(self._logo_card, 0, 1)
        cards.addWidget(self._track_card, 1, 0)
        cards.addWidget(self._run_dir_card, 1, 1)

    def bind_asset_summary(
        self,
        *,
        background_path: str,
        background_source_label: str,
        logo_path: str,
        track_path: str,
        track_detail: str,
        run_directory: str,
    ) -> None:
        self._background_card.bind(
            value=_file_name(background_path),
            detail=(
                f"{background_source_label} · {background_path}"
                if background_path
                else background_source_label
            ),
            ready=bool(background_path),
        )
        self._logo_card.bind(
            value=_file_name(logo_path),
            detail=logo_path or "Select a logo in the Logo tab",
            ready=bool(logo_path),
        )
        track_label = _file_name(track_path, fallback="No track selected")
        self._track_card.bind(
            value=track_label,
            detail=track_detail or track_path or "Select an MP3 for preview transport",
            ready=bool(track_path),
        )
        self._run_dir_card.bind(
            value=_file_name(run_directory, fallback="No run directory"),
            detail=run_directory or "No resolved run directory",
            ready=bool(run_directory),
        )
