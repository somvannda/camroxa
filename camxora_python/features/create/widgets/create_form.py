"""Advanced Create form: lyrics, styles, options, generate CTA."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from features.create.constants import EDITOR_HEIGHT, GENERATE_BUTTON_HEIGHT
from features.create.widgets.icons import create_icon
from features.create.widgets.studio_controls import ModeTab, StudioCheckBox, StudioComboBox, StudioRadioButton
from shared.lib.ui_font import content_font, studio_font


class GenerateButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("  Generate Music", parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(GENERATE_BUTTON_HEIGHT)
        self.setFont(studio_font(12, QFont.Weight.DemiBold))
        self.setIcon(create_icon("sparkles", size=14, color="#FFFFFF"))
        self.setIconSize(QSize(14, 14))
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        gradient = QLinearGradient(0, 0, float(self.width()), 0)
        if self.isEnabled():
            if self.underMouse():
                gradient.setColorAt(0.0, QColor("#7C3AED"))
                gradient.setColorAt(0.5, QColor("#22D3EE"))
                gradient.setColorAt(1.0, QColor("#10D98A"))
            else:
                gradient.setColorAt(0.0, QColor("#6536DD"))
                gradient.setColorAt(0.5, QColor("#23B8D8"))
                gradient.setColorAt(1.0, QColor("#00C878"))
        else:
            gradient.setColorAt(0.0, QColor("#3A2A6A"))
            gradient.setColorAt(1.0, QColor("#1A4A3A"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 5, 5)

        icon = self.icon().pixmap(14, 14)
        text = self.text().strip()
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(studio_font(12, QFont.Weight.DemiBold))
        text_width = painter.fontMetrics().horizontalAdvance(text)
        total = 14 + 6 + text_width
        x = (self.width() - total) // 2
        y = (self.height() - 14) // 2
        painter.drawPixmap(x, y, icon)
        painter.drawText(x + 20, 0, text_width + 4, self.height(), int(Qt.AlignmentFlag.AlignVCenter), text)


class _EditorBlock(QWidget):
    def __init__(self, title: str, placeholder: str, maximum: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EditorBlock")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(placeholder)
        self.editor.setFont(content_font(12))
        self.editor.setMinimumHeight(EDITOR_HEIGHT)
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.editor, 1)
        self.counter = QLabel(f"0 / {maximum:,}")
        self.counter.setObjectName("CharCount")
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.counter)
        self._maximum = maximum
        self.editor.textChanged.connect(self._update_count)

    def _update_count(self) -> None:
        text = self.editor.toPlainText()
        if len(text) > self._maximum:
            cursor = self.editor.textCursor()
            self.editor.blockSignals(True)
            self.editor.setPlainText(text[: self._maximum])
            self.editor.blockSignals(False)
            self.editor.setTextCursor(cursor)
            text = text[: self._maximum]
        self.counter.setText(f"{len(text):,} / {self._maximum:,}")


class _OptionSlider(QWidget):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TransparentBlock")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        header = QHBoxLayout()
        name = QLabel(label)
        name.setObjectName("FieldLabel")
        self.value = QLabel("50%")
        self.value.setObjectName("FieldLabel")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(name)
        header.addStretch(1)
        header.addWidget(self.value)
        layout.addLayout(header)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(lambda v: self.value.setText(f"{v}%"))
        layout.addWidget(self.slider)


class CreateForm(QFrame):
    generate_requested = Signal()
    folder_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        tab_bar = QFrame()
        tab_bar.setObjectName("ModeTabBar")
        tab_inner = QHBoxLayout(tab_bar)
        tab_inner.setContentsMargins(4, 4, 4, 4)
        tab_inner.setSpacing(4)
        self.simple_tab = ModeTab("Simple")
        self.advanced_tab = ModeTab("Advanced")
        self.advanced_tab.setChecked(True)
        self.simple_tab.clicked.connect(lambda: self._set_mode("simple"))
        self.advanced_tab.clicked.connect(lambda: self._set_mode("advanced"))
        tab_inner.addWidget(self.simple_tab)
        tab_inner.addWidget(self.advanced_tab)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(8)
        tab_row.addWidget(tab_bar)
        tab_row.addStretch(1)
        self.model = StudioComboBox()
        self.model.addItems(["V5.5", "V5", "V4.5"])
        self.model.setFixedWidth(92)
        tab_row.addWidget(self.model)
        root.addLayout(tab_row)

        self._editors = QWidget()
        self._editors.setObjectName("EditorPair")
        self._editors.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._editors.setAutoFillBackground(False)
        self._editors.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        editors = QHBoxLayout(self._editors)
        editors.setContentsMargins(0, 0, 0, 0)
        editors.setSpacing(10)
        self.lyrics = _EditorBlock(
            "LYRICS",
            "Lyrics are drafted automatically for each song when you Generate",
            5000,
        )
        self.styles = _EditorBlock(
            "STYLES",
            "urbano, electric guitar, upbeat rock, 128 BPM, eurodance",
            1000,
        )
        editors.addWidget(self.lyrics, 1)
        editors.addWidget(self.styles, 1)
        root.addWidget(self._editors, 1)

        more = QLabel("MORE OPTIONS")
        more.setObjectName("SectionLabel")
        root.addWidget(more)

        self.title = QLineEdit()
        self.title.setObjectName("SongTitle")
        self.title.setPlaceholderText("Song Title (Optional)")
        self.title.setFont(content_font(12))
        self._title_block = self._field_block("Song title (optional)", self.title)
        root.addWidget(self._title_block)

        options = QHBoxLayout()
        options.setSpacing(16)
        options.addLayout(self._left_options(), 1)
        options.addLayout(self._right_options(), 1)
        root.addLayout(options)

        templates = QHBoxLayout()
        templates.setSpacing(10)
        self.version1 = StudioComboBox()
        self.version1.addItems(["None", "Cinematic", "Pop vocal", "Lo-fi"])
        self.version2 = StudioComboBox()
        self.version2.addItems(["None", "Cinematic", "Pop vocal", "Lo-fi"])
        templates.addLayout(self._stack("Version 1 template", self.version1), 1)
        templates.addLayout(self._stack("Version 2 template", self.version2), 1)
        root.addLayout(templates)

        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        self.folder_button = QPushButton("  Choose a Save to folder")
        self.folder_button.setObjectName("SecondaryButton")
        self.folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_button.setIcon(create_icon("folder-open", size=14, color="#8FA4BB"))
        self.folder_button.setIconSize(QSize(14, 14))
        self.folder_button.clicked.connect(self._choose_folder)
        self.save_path = QLineEdit()
        self.save_path.setReadOnly(True)
        self.save_path.setPlaceholderText("No folder selected")
        save_row.addWidget(self.folder_button)
        save_row.addWidget(self.save_path, 1)
        root.addLayout(save_row)

        self.generate = GenerateButton()
        self.generate.clicked.connect(self.generate_requested.emit)
        root.addWidget(self.generate)

    def _set_mode(self, mode: str) -> None:
        self.simple_tab.setChecked(mode == "simple")
        self.advanced_tab.setChecked(mode == "advanced")
        advanced = mode == "advanced"
        self._editors.setVisible(True)
        self._negative_block.setVisible(advanced)
        self._gender_block.setVisible(advanced)
        self.style_influence.setVisible(advanced)
        self.weirdness.setVisible(advanced)
        self.audio_weight.setVisible(advanced)
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.setStretchFactor(self._editors, 1)

    def _stack(self, label: str, widget: QWidget) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        caption = QLabel(label)
        caption.setObjectName("FieldLabel")
        box.addWidget(caption)
        box.addWidget(widget)
        return box

    def _field_block(self, label: str, widget: QWidget) -> QWidget:
        block = QWidget()
        block.setObjectName("TransparentBlock")
        block.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        block.setAutoFillBackground(False)
        block.setLayout(self._stack(label, widget))
        return block

    def _check(self, text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(StudioCheckBox(text))
        row.addStretch(1)
        return row

    def _left_options(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self.negative = QLineEdit()
        self.negative.setObjectName("NegativeTags")
        self.negative.setPlaceholderText("choir, backing vocals, falsetto")
        self.negative.setFont(content_font(12))
        self._negative_block = self._field_block("Negative tags (optional)", self.negative)
        col.addWidget(self._negative_block)
        self.versions = StudioComboBox()
        self.versions.addItems(["Shuffle versions", "Keep versions", "Version 1 only"])
        col.addLayout(self._stack("Versions", self.versions))
        for label in (
            "Download WAV",
            "Download LRC",
            "Download SRT",
            "Auto image",
            "Auto video",
            "Merge all video",
        ):
            col.addLayout(self._check(label))
        return col

    def _right_options(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self._gender_block = QWidget()
        self._gender_block.setObjectName("TransparentBlock")
        self._gender_block.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._gender_block.setAutoFillBackground(False)
        gender_col = QVBoxLayout(self._gender_block)
        gender_col.setContentsMargins(0, 0, 0, 0)
        gender_col.setSpacing(6)
        gender_label = QLabel("Vocal Gender")
        gender_label.setObjectName("FieldLabel")
        gender_col.addWidget(gender_label)
        gender = QHBoxLayout()
        gender.setSpacing(16)
        self.gender_group = QButtonGroup(self)
        for index, name in enumerate(("Male", "Female", "Both")):
            radio = StudioRadioButton(name)
            if index == 0:
                radio.setChecked(True)
            self.gender_group.addButton(radio)
            gender.addWidget(radio)
        gender.addStretch(1)
        gender_col.addLayout(gender)
        col.addWidget(self._gender_block)
        self.style_influence = _OptionSlider("Style Influence")
        self.weirdness = _OptionSlider("Weirdness")
        self.audio_weight = _OptionSlider("Audio Weight")
        col.addWidget(self.style_influence)
        col.addWidget(self.weirdness)
        col.addWidget(self.audio_weight)
        return col

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a Save to folder")
        if path:
            self.save_path.setText(path)
            self.folder_changed.emit(path)

    def set_generating(self, busy: bool) -> None:
        self.generate.setEnabled(not busy)
        self.generate.setText("  Generating…" if busy else "  Generate Music")
