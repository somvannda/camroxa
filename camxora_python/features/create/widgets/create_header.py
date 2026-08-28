"""Create page title row."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from features.create.constants import CREATE_HEADER_HEIGHT


class CreateHeader(QFrame):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "Create",
        subtitle: str = "Generate songs with the web Create form, then automate image and video locally.",
        meta: str = "1 planned day · 4 songs",
        eyebrow: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CreateHeader")
        if eyebrow:
            self.setMinimumHeight(CREATE_HEADER_HEIGHT)
        else:
            self.setFixedHeight(CREATE_HEADER_HEIGHT)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 10)
        root.setSpacing(12)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(2)
        if eyebrow:
            eye = QLabel(eyebrow)
            eye.setObjectName("FieldLabel")
            copy.addWidget(eye)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        caption = QLabel(subtitle)
        caption.setObjectName("PageSubtitle")
        copy.addWidget(heading)
        copy.addWidget(caption)
        root.addLayout(copy, 1)

        self._meta = QLabel(meta)
        self._meta.setObjectName("PlanMeta")
        self._meta.setVisible(bool(meta))
        root.addWidget(self._meta)
