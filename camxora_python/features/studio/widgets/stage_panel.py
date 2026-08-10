"""Studio center stage — Video-style preview + playback + export console."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from features.studio.widgets.export_panel import StudioExportPanel
from features.studio.widgets.preview_stage import StudioPreviewStage
from features.studio.widgets.track_list import StudioTrackList
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, START_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel


def _format_time(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0))))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


class StudioStagePanel(SettingsPanel):
    """Center column matching VideoStagePanel structure."""

    play_toggled = Signal(bool)
    stop_requested = Signal()
    seek_requested = Signal(float)
    seek_relative_requested = Signal(float)
    repeat_toggled = Signal(bool)
    track_selected = Signal(str)
    add_tracks_requested = Signal()
    remove_track_requested = Signal(str)
    export_json_requested = Signal()
    export_video_requested = Signal()
    export_options_changed = Signal(dict)
    browse_assets_requested = Signal()
    spectrum_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    spectrum_size_delta_requested = Signal(float)
    playback_state_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", fill_available_height=True, parent=parent)
        self._duration = 0.0
        self._position = 0.0
        self._scrubbing = False
        self._playing = False

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title = QLabel("Preview")
        header_layout.addWidget(title)
        header_layout.addStretch()
        browse = QPushButton("Browse assets")
        browse.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        browse.clicked.connect(self.browse_assets_requested.emit)
        header_layout.addWidget(browse)
        self.add_widget(header)

        self._preview = StudioPreviewStage()
        self._preview.spectrum_position_changed.connect(self.spectrum_position_changed.emit)
        self._preview.logo_position_changed.connect(self.logo_position_changed.emit)
        self._preview.spectrum_size_delta_requested.connect(self.spectrum_size_delta_requested.emit)
        self._preview.playback_state_changed.connect(self._on_preview_playback_state)
        # Status line lives on preview stage; keep stage chrome Video-like.
        self.add_widget(self._preview, stretch=2)

        self._play_btn = QPushButton("Play")
        self._play_btn.setObjectName(START_BUTTON_ID)
        self._play_btn.clicked.connect(self._toggle_playback)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._stop_btn.clicked.connect(self._on_stop)
        self._repeat_btn = QPushButton("Repeat")
        self._repeat_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._repeat_btn.setCheckable(True)
        self._repeat_btn.setToolTip("Repeat track when it ends")
        self._repeat_btn.toggled.connect(self._on_repeat_toggled)
        self._back_btn = QPushButton("Backward")
        self._back_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._back_btn.clicked.connect(lambda: self.seek_relative_requested.emit(-10.0))
        self._fwd_btn = QPushButton("Forward")
        self._fwd_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._fwd_btn.clicked.connect(lambda: self.seek_relative_requested.emit(10.0))
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName(SUBTITLE_LABEL_ID)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.valueChanged.connect(self._on_seek_changed)

        playback = QFrame()
        playback.setObjectName("account_card")
        playback_layout = QVBoxLayout(playback)
        playback_layout.setContentsMargins(10, 8, 10, 8)
        playback_layout.setSpacing(4)
        playback_title = QLabel("Playback")
        playback_title.setObjectName(SUBTITLE_LABEL_ID)
        playback_layout.addWidget(playback_title)
        self._track_label = QLabel("No track selected")
        self._track_label.setObjectName(SUBTITLE_LABEL_ID)
        self._track_label.setWordWrap(True)
        playback_layout.addWidget(self._track_label)
        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(6)
        transport.addWidget(self._back_btn)
        transport.addWidget(self._play_btn)
        transport.addWidget(self._stop_btn)
        transport.addWidget(self._repeat_btn)
        transport.addWidget(self._fwd_btn)
        transport.addWidget(self._time_label)
        transport.addStretch()
        playback_layout.addLayout(transport)
        playback_layout.addWidget(self._seek_slider)
        self.add_widget(playback)

        console = QWidget()
        console_layout = QHBoxLayout(console)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(10)
        self._tracks = StudioTrackList()
        self._tracks.track_selected.connect(self.track_selected.emit)
        self._tracks.add_tracks_requested.connect(self.add_tracks_requested.emit)
        self._tracks.remove_track_requested.connect(self.remove_track_requested.emit)
        console_layout.addWidget(self._tracks, 1)
        self._export = StudioExportPanel()
        self._export.options_changed.connect(self.export_options_changed.emit)
        self._export.export_json_requested.connect(self.export_json_requested.emit)
        self._export.export_video_requested.connect(self.export_video_requested.emit)
        console_layout.addWidget(self._export, 1)
        self.add_widget(console, stretch=1)

    def set_interaction_modes(self, *, spectrum_position: bool = False, logo_position: bool = False) -> None:
        self._preview.set_interaction_modes(
            spectrum_position=spectrum_position,
            logo_position=logo_position,
        )

    def preview(self) -> StudioPreviewStage:
        return self._preview

    def export_panel(self) -> StudioExportPanel:
        return self._export

    def bind_tracks(self, tracks: list[str], active_path: str = "") -> None:
        active = str(active_path or "").strip()
        self._tracks.set_tracks(tracks, active)
        if active:
            try:
                self._track_label.setText(Path(active).name or active)
            except Exception:
                self._track_label.setText(active)
            self._track_label.setToolTip(active)
        else:
            self._track_label.setText("No track selected")
            self._track_label.setToolTip("")

    def set_export_busy(self, busy: bool) -> None:
        self._export.set_export_busy(busy)

    def set_export_readiness(self, ok: bool, message: str = "") -> None:
        self._export.set_readiness(ok, message)

    def bind_export(self, state: dict) -> None:
        self._export.bind(state)

    def export_options(self) -> dict:
        return self._export.options()

    def set_duration(self, duration_sec: float) -> None:
        self._duration = max(0.0, float(duration_sec or 0.0))
        self._render_time()

    def set_position(self, time_sec: float) -> None:
        if self._scrubbing:
            return
        self._position = max(0.0, float(time_sec or 0.0))
        if self._duration > 0:
            blocked = self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(
                int(max(0, min(1000, round((self._position / self._duration) * 1000))))
            )
            self._seek_slider.blockSignals(blocked)
        self._render_time()

    def set_playing(self, playing: bool) -> None:
        self._playing = bool(playing)
        self._play_btn.setText("Pause" if self._playing else "Play")

    def set_repeat(self, enabled: bool) -> None:
        blocked = self._repeat_btn.blockSignals(True)
        self._repeat_btn.setChecked(bool(enabled))
        self._repeat_btn.blockSignals(blocked)
        self._preview.set_loop_playback(bool(enabled))

    def _toggle_playback(self) -> None:
        self.set_playing(not self._playing)
        self.play_toggled.emit(self._playing)

    def _on_stop(self) -> None:
        self.set_playing(False)
        self.stop_requested.emit()

    def _on_repeat_toggled(self, checked: bool) -> None:
        self._preview.set_loop_playback(bool(checked))
        self.repeat_toggled.emit(bool(checked))

    def _on_preview_playback_state(self, payload: object) -> None:
        self.playback_state_changed.emit(payload)
        if not isinstance(payload, dict):
            return
        playing = bool(payload.get("isPlaying"))
        if playing != self._playing:
            self.set_playing(playing)
        try:
            dur = float(payload.get("durationSec") or 0.0)
            pos = float(payload.get("currentTimeSec") or 0.0)
        except (TypeError, ValueError):
            return
        if dur > 0:
            self.set_duration(dur)
        self.set_position(pos)

    def _on_seek_pressed(self) -> None:
        self._scrubbing = True

    def _on_seek_released(self) -> None:
        self._scrubbing = False
        if self._duration <= 0:
            return
        self.seek_requested.emit((self._seek_slider.value() / 1000.0) * self._duration)

    def _on_seek_changed(self, value: int) -> None:
        if not self._scrubbing or self._duration <= 0:
            return
        self.seek_requested.emit((value / 1000.0) * self._duration)

    def _render_time(self) -> None:
        shown = self._position
        if self._duration > 0:
            shown = min(shown, self._duration)
        self._time_label.setText(f"{_format_time(shown)} / {_format_time(self._duration)}")
