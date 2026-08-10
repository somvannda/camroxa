"""Studio export actions — Video-style Actions card under the stage."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from features.studio.widgets.axis_combo import populate_combo, set_combo_data
from features.video.lib.render_scene_request import EXPORT_FPS_CHOICES
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, START_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import form_row

_RESOLUTIONS: tuple[tuple[str, str], ...] = (
    ("1280x720", "720p"),
    ("1920x1080", "1080p"),
    ("1080x1920", "Reel 9:16"),
    ("3840x2160", "4K"),
)

_QUALITY: tuple[tuple[str, str], ...] = (
    ("very_fast", "Very fast"),
    ("fast", "Fast"),
    ("balanced", "Balanced / quality"),
)


def _spin(*, minimum: float, maximum: float, step: float, value: float = 0.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setSingleStep(step)
    box.setDecimals(1)
    box.setValue(value)
    box.setSuffix(" s")
    return box


class StudioExportPanel(QFrame):
    """Export controls for Composition Studio (Video Actions-card pattern)."""

    options_changed = Signal(dict)
    export_json_requested = Signal()
    export_video_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("account_card")
        self._binding = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        title = QLabel("Actions")
        title.setObjectName(SUBTITLE_LABEL_ID)
        root.addWidget(title)

        self._resolution = QComboBox()
        populate_combo(self._resolution, _RESOLUTIONS, include_none=False)
        set_combo_data(self._resolution, "1920x1080", fallback="1920x1080")
        self._resolution.currentIndexChanged.connect(self._emit)
        root.addWidget(form_row("Resolution", self._resolution))

        fps_opts = tuple((str(v), f"{v} fps") for v in EXPORT_FPS_CHOICES)
        self._fps = QComboBox()
        populate_combo(self._fps, fps_opts, include_none=False)
        set_combo_data(self._fps, "24", fallback="24")
        self._fps.currentIndexChanged.connect(self._emit)
        root.addWidget(form_row("Frame rate", self._fps))

        self._quality = QComboBox()
        populate_combo(self._quality, _QUALITY, include_none=False)
        set_combo_data(self._quality, "fast", fallback="fast")
        self._quality.currentIndexChanged.connect(self._emit)
        root.addWidget(form_row("Quality", self._quality))

        self._include_audio = QCheckBox("Include audio in export")
        self._include_audio.setChecked(True)
        self._include_audio.toggled.connect(lambda _v: self._emit())
        root.addWidget(self._include_audio)

        range_host = QWidget()
        range_row = QHBoxLayout(range_host)
        range_row.setContentsMargins(0, 0, 0, 0)
        range_row.setSpacing(8)
        self._range_start = _spin(minimum=0.0, maximum=36000.0, step=0.5, value=0.0)
        self._range_end = _spin(minimum=0.0, maximum=36000.0, step=0.5, value=0.0)
        self._range_start.valueChanged.connect(lambda _v: self._emit())
        self._range_end.valueChanged.connect(lambda _v: self._emit())
        range_row.addWidget(QLabel("Start"))
        range_row.addWidget(self._range_start, stretch=1)
        range_row.addWidget(QLabel("End (0 = full)"))
        range_row.addWidget(self._range_end, stretch=1)
        root.addWidget(form_row("Range", range_host))

        export_row = QHBoxLayout()
        export_row.setSpacing(6)
        self._export_json_btn = QPushButton("Export JSON")
        self._export_json_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._export_json_btn.clicked.connect(self.export_json_requested.emit)
        self._export_video_btn = QPushButton("Export Video")
        self._export_video_btn.setObjectName(START_BUTTON_ID)
        self._export_video_btn.clicked.connect(self.export_video_requested.emit)
        export_row.addWidget(self._export_json_btn, 1)
        export_row.addWidget(self._export_video_btn, 1)
        root.addLayout(export_row)

        self._readiness = QLabel("Select audio + background to export.")
        self._readiness.setObjectName(SUBTITLE_LABEL_ID)
        self._readiness.setWordWrap(True)
        root.addWidget(self._readiness)
        self._summary = QLabel("")
        self._summary.setObjectName(SUBTITLE_LABEL_ID)
        self._summary.setWordWrap(True)
        root.addWidget(self._summary)
        root.addStretch(1)
        self._refresh_summary()

    def options(self) -> dict:
        try:
            fps = int(self._fps.currentData() or "24")
        except (TypeError, ValueError):
            fps = 24
        return {
            "resolution": self._resolution.currentData() or "1920x1080",
            "fps": fps,
            "quality": self._quality.currentData() or "fast",
            "includeAudio": bool(self._include_audio.isChecked()),
            "rangeStart": float(self._range_start.value()),
            "rangeEnd": float(self._range_end.value()),
        }

    def bind(self, state: dict) -> None:
        self._binding = True
        export = state.get("studioExport") if isinstance(state.get("studioExport"), dict) else {}
        set_combo_data(
            self._resolution, str(export.get("resolution") or "1920x1080"), fallback="1920x1080"
        )
        set_combo_data(self._fps, str(int(export.get("fps") or 24)), fallback="24")
        set_combo_data(self._quality, str(export.get("quality") or "fast"), fallback="fast")
        self._include_audio.setChecked(bool(export.get("includeAudio", True)))
        self._range_start.setValue(float(export.get("rangeStart") or 0.0))
        self._range_end.setValue(float(export.get("rangeEnd") or 0.0))
        self._binding = False
        self._refresh_summary()

    def set_readiness(self, ok: bool, message: str) -> None:
        if ok:
            self._readiness.setText("Ready to export video.")
        else:
            self._readiness.setText(message or "Not ready to export.")

    def set_export_busy(self, busy: bool) -> None:
        self._export_video_btn.setEnabled(not busy)
        self._export_json_btn.setEnabled(not busy)
        self._export_video_btn.setText("Exporting…" if busy else "Export Video")

    def _emit(self, *_args) -> None:
        if self._binding:
            return
        self._refresh_summary()
        self.options_changed.emit(self.options())

    def _refresh_summary(self) -> None:
        opts = self.options()
        end = float(opts["rangeEnd"])
        span = "full track" if end <= 0 else f"{opts['rangeStart']:.1f}s → {end:.1f}s"
        audio = "with audio" if opts["includeAudio"] else "video only"
        self._summary.setText(
            f"{opts['resolution']} · {opts['fps']} fps · {opts['quality']} · {audio} · {span}"
        )
