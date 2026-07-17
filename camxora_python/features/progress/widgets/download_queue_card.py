"""Desktop download queue card — standard account_card."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from shared.models.platform import PendingMusicDownloadItem
from shared.themes.deep_blue import SUBTITLE_LABEL_ID

SUBTITLE = (
    "Recent Suno MP3 downloads for batches from the last 30 days. "
    "Older backlog and items without a local target folder are hidden."
)


class DownloadQueueCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DESKTOP DOWNLOAD QUEUE")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        subtitle = QLabel(SUBTITLE)
        subtitle.setObjectName(SUBTITLE_LABEL_ID)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self._count_label = QLabel("0 pending")
        self._count_label.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(self._count_label)

        self._items_layout = QVBoxLayout()
        self._items_layout.setSpacing(8)
        root.addLayout(self._items_layout)

    def set_items(self, items: list[PendingMusicDownloadItem]) -> None:
        while self._items_layout.count():
            child = self._items_layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()

        count = len(items)
        suffix = "" if count == 1 else "s"
        self._count_label.setText(f"{count} pending download{suffix}")
        self.setVisible(count > 0)

        for item in items:
            self._items_layout.addWidget(self._build_item(item))

    def _build_item(self, item: PendingMusicDownloadItem) -> QWidget:
        frame = QFrame()
        frame.setObjectName("account_card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        header = QLabel(
            f"{item.title or 'Untitled track'} · #{item.track_number or '—'} · "
            f"{(item.batch_id or 'batch')[-8:]}"
        )
        header.setObjectName(SUBTITLE_LABEL_ID)
        header.setWordWrap(True)
        layout.addWidget(header)

        primary = QLabel(f"Primary: {item.primary.target_path or 'No target path yet'}")
        primary.setObjectName(SUBTITLE_LABEL_ID)
        primary.setWordWrap(True)
        layout.addWidget(primary)

        secondary = QLabel(f"Secondary: {item.secondary.target_path or 'No target path yet'}")
        secondary.setObjectName(SUBTITLE_LABEL_ID)
        secondary.setWordWrap(True)
        layout.addWidget(secondary)

        return frame
