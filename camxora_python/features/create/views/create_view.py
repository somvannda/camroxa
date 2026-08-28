"""Create workspace page inside the existing desktop shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QSplitter, QVBoxLayout, QWidget

from features.create.constants import FILES_PANEL_MIN_WIDTH, FORM_SPLIT_RATIO
from features.create.create_styles import build_create_page_qss
from features.create.services.audio_service import AudioService
from features.create.services.generation_service import GenerationService
from features.create.widgets.create_form import CreateForm
from features.create.widgets.create_header import CreateHeader
from features.create.widgets.file_panel import FilePanel
from features.create.widgets.planning_bar import PlanningBar
from shared.lib.ui_font import ensure_khmer_siemreap_loaded, studio_font
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache


class CreateView(QWidget):
    """Same Create form / Files / player as the standalone preview."""

    def __init__(
        self,
        api: PlatformApi | None = None,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("create_workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ensure_khmer_siemreap_loaded()
        self.setStyleSheet(build_create_page_qss())
        self.setFont(studio_font(12))
        self._api = api
        self._cache = cache
        self._audio = AudioService(self)
        self._generation = GenerationService(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.page_header = CreateHeader()
        self.planning = PlanningBar()
        root.addWidget(self.page_header)
        root.addWidget(self.planning)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(10)
        self.form = CreateForm()
        self.files = FilePanel()
        self.form.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.files.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.form.setMinimumWidth(420)
        self.files.setMinimumWidth(FILES_PANEL_MIN_WIDTH)
        self.splitter.addWidget(self.form)
        self.splitter.addWidget(self.files)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 6)
        self.splitter.setStretchFactor(1, 4)
        root.addWidget(self.splitter, 1)
        self._apply_split_ratio()

        self.form.generate_requested.connect(self._generation.start)
        self._generation.started.connect(lambda: self.form.set_generating(True))
        self._generation.finished.connect(self._generation_finished)
        self.files.track_selected.connect(self._audio.set_track)
        self.files.player.play_clicked.connect(self._audio.toggle)
        self.files.player.stop_clicked.connect(self._audio.stop)
        self.files.player.back_clicked.connect(lambda: self.files.select_relative(-1))
        self.files.player.next_clicked.connect(lambda: self.files.select_relative(1))
        self.files.player.seeked.connect(self._audio.seek)
        self._audio.track_changed.connect(self.files.player.set_track)
        self._audio.playing_changed.connect(self.files.player.set_playing)
        self._audio.position_changed.connect(self.files.player.set_position)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._apply_split_ratio()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_split_ratio()

    def _apply_split_ratio(self) -> None:
        width = self.splitter.width()
        if width <= 1:
            return
        form = int(round(width * FORM_SPLIT_RATIO / 100))
        self.splitter.setSizes([form, width - form])

    def _generation_finished(self) -> None:
        self.form.set_generating(False)
        self._generation.busy = False
