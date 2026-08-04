"""Video workspace center stage — live GPU preview (Phase 9d/9e)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from shared.lib.output_resolutions import OUTPUT_RESOLUTION_OPTIONS, OUTPUT_RESOLUTION_VALUES
from shared.models.desktop import VideoPlaybackState
from shared.themes.deep_blue import SETTINGS_SECONDARY_BUTTON_ID, START_BUTTON_ID, SUBTITLE_LABEL_ID
from shared.widgets.settings_ui import SettingsPanel
from features.video.widgets.text_drag_overlay import TextDragOverlay

try:
    from visualizer.preview_widget import AspectRatioBox, VideoSpectrumPreview

    _GPU_PREVIEW_AVAILABLE = True
    _GPU_PREVIEW_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - optional GPU stack
    AspectRatioBox = None  # type: ignore[misc, assignment]
    VideoSpectrumPreview = None  # type: ignore[misc, assignment]
    _GPU_PREVIEW_AVAILABLE = False
    _GPU_PREVIEW_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def gpu_preview_install_hint() -> str:
    """User-facing guidance when the live preview stack failed to import."""
    from shared.lib.runtime_paths import is_frozen_runtime

    detail = f"\n\nTechnical detail: {_GPU_PREVIEW_IMPORT_ERROR}" if _GPU_PREVIEW_IMPORT_ERROR else ""
    if is_frozen_runtime():
        return (
            "Live video preview could not start on this PC.\n"
            "Reinstall Camxora from the latest installer, or contact support if this continues."
            f"{detail}"
        )
    return (
        "Live video preview could not load its graphics stack.\n"
        "For local development, reinstall the desktop package so GPU libs are present:\n"
        "  pip install -e .\n"
        "(Packaged Camxora.exe already includes these — end users never run pip.)"
        f"{detail}"
    )


def _existing_file_path(path: str) -> str:
    candidate = str(path or "").strip()
    if not candidate:
        return ""
    try:
        return candidate if Path(candidate).is_file() else ""
    except OSError:
        return ""


def _format_time_label(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0))))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


class VideoStagePanel(SettingsPanel):
    playback_command_requested = Signal(str)
    playback_seek_requested = Signal(float)
    spectrum_position_changed = Signal(int, int)
    lightning_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    background_transform_changed = Signal(float, float, float)
    text_domain_position_changed = Signal(str, float, float)
    # domain, patch dict (boxWidth / fontSize / letterSpacing / x / y)
    text_domain_box_resized = Signal(str, object)
    text_domain_box_resize_changed = Signal(str, object)
    playback_state_changed = Signal(object)
    output_resolution_changed = Signal(str)
    select_background_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        # python_app center column: header row (title + resolution +
        # Background), preview (stretch 2), then Playback and Export Queue.
        super().__init__(
            "",
            fill_available_height=True,
            parent=parent,
        )
        self._fallback: QLabel | None = None
        self._preview_host: QWidget | None = None
        self._preview: VideoSpectrumPreview | None = None
        self._aspect_box: AspectRatioBox | None = None
        self._text_drag_overlay: TextDragOverlay | None = None
        self._background_path = ""
        self._logo_path = ""
        self._mp3_path = ""
        self._playback = VideoPlaybackState()
        self._seek_dragging = False
        self._preview_runtime_nonce = 0
        self._last_template: dict | None = None
        self._last_template_key = ""
        self._last_preview_args: dict | None = None
        self._resolution_pending = False
        self._current_track_path = ""
        self._track_label: QLabel | None = None
        self._active_text_domain = ""

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self._preview_title = QLabel("Preview")
        header_layout.addWidget(self._preview_title)
        header_layout.addStretch()
        self._resolution_combo = QComboBox()
        for value, label in OUTPUT_RESOLUTION_OPTIONS:
            self._resolution_combo.addItem(label, value)
        self._resolution_combo.currentIndexChanged.connect(self._on_resolution_changed)
        header_layout.addWidget(self._resolution_combo)
        background_btn = QPushButton("Background")
        background_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        background_btn.clicked.connect(self.select_background_requested.emit)
        header_layout.addWidget(background_btn)
        self.add_widget(header)

        self._play_btn = QPushButton("Play")
        self._play_btn.setObjectName(START_BUTTON_ID)
        self._play_btn.clicked.connect(self._toggle_playback)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._stop_btn.clicked.connect(lambda: self.playback_command_requested.emit("stop"))
        self._back_btn = QPushButton("Backward")
        self._back_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._back_btn.clicked.connect(lambda: self._seek_relative(-10.0))
        self._fwd_btn = QPushButton("Forward")
        self._fwd_btn.setObjectName(SETTINGS_SECONDARY_BUTTON_ID)
        self._fwd_btn.clicked.connect(lambda: self._seek_relative(10.0))
        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setObjectName(SUBTITLE_LABEL_ID)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self._seek_slider.sliderReleased.connect(self._on_seek_released)
        self._seek_slider.valueChanged.connect(self._on_seek_changed)

        if _GPU_PREVIEW_AVAILABLE and VideoSpectrumPreview is not None and AspectRatioBox is not None:
            self._preview = VideoSpectrumPreview()
            self._aspect_box = AspectRatioBox(self._preview, ratio_w=16, ratio_h=9)
            self._text_drag_overlay = TextDragOverlay()
            self._wire_text_drag_overlay()
            self._aspect_box.set_overlay(self._text_drag_overlay)
            self._preview_host = self._aspect_box
            self._wire_preview_signals()
            self.add_widget(self._preview_host, stretch=2)
        else:
            body = QWidget()
            layout = QVBoxLayout(body)
            layout.setContentsMargins(0, 0, 0, 0)
            self._fallback = QLabel(gpu_preview_install_hint())
            self._fallback.setObjectName(SUBTITLE_LABEL_ID)
            self._fallback.setWordWrap(True)
            self._fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addStretch()
            layout.addWidget(self._fallback)
            layout.addStretch()
            self.add_widget(body, stretch=2)
            self._play_btn.setEnabled(False)
            self._stop_btn.setEnabled(False)
            self._back_btn.setEnabled(False)
            self._fwd_btn.setEnabled(False)
            self._seek_slider.setEnabled(False)

        playback_section = QFrame()
        playback_section.setObjectName("account_card")
        playback_layout = QVBoxLayout(playback_section)
        playback_layout.setContentsMargins(10, 8, 10, 8)
        playback_layout.setSpacing(4)
        playback_title = QLabel("Playback")
        playback_title.setObjectName(SUBTITLE_LABEL_ID)
        playback_layout.addWidget(playback_title)
        self._track_label = QLabel("No track selected")
        self._track_label.setObjectName(SUBTITLE_LABEL_ID)
        self._track_label.setWordWrap(True)
        playback_layout.addWidget(self._track_label)
        transport_row = QHBoxLayout()
        transport_row.setContentsMargins(0, 0, 0, 0)
        transport_row.setSpacing(6)
        transport_row.addWidget(self._back_btn)
        transport_row.addWidget(self._play_btn)
        transport_row.addWidget(self._stop_btn)
        transport_row.addWidget(self._fwd_btn)
        transport_row.addWidget(self._time_label)
        transport_row.addStretch()
        playback_layout.addLayout(transport_row)
        playback_layout.addWidget(self._seek_slider)
        self.add_widget(playback_section)

        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(500)
        self._playback_timer.timeout.connect(self._refresh_playback_ui)

    def mount_export_panel(self, panel: QWidget) -> None:
        """Dock the export queue console under the playback section."""
        self.add_widget(panel, stretch=1)

    def _seek_relative(self, delta_sec: float) -> None:
        duration = float(max(0.0, self._playback.duration_sec))
        if duration <= 0:
            return
        target = float(self._playback.current_time_sec) + float(delta_sec)
        self.playback_seek_requested.emit(max(0.0, min(duration, target)))

    def gpu_preview_available(self) -> bool:
        return _GPU_PREVIEW_AVAILABLE and self._preview is not None

    def preview_widget(self):
        return self._preview

    def preview_runtime_nonce(self) -> int:
        return int(self._preview_runtime_nonce)

    def preview_lifecycle_snapshot(self) -> dict:
        if not self.gpu_preview_available() or self._preview is None:
            return {
                "status": "unsupported",
                "message": "GPU preview dependencies are not available in this environment.",
            }
        return self._preview.preview_lifecycle_snapshot()

    def performance_snapshot(self) -> dict:
        if self._preview is None:
            return {"frameMs": 0.0, "fps": 0.0, "frameCounter": 0, "glReady": False}
        return self._preview.performance_snapshot()

    def remount_preview(self) -> int:
        self._preview_runtime_nonce += 1
        if not _GPU_PREVIEW_AVAILABLE or self._aspect_box is None:
            return self._preview_runtime_nonce
        if self._preview is not None:
            try:
                self._preview.stop_preview()
            except Exception:
                pass
            self._preview.setParent(None)
            self._preview.deleteLater()
            self._preview = None
        self._preview = VideoSpectrumPreview()
        self._aspect_box.replace_child(self._preview)
        if self._text_drag_overlay is None:
            self._text_drag_overlay = TextDragOverlay()
            self._wire_text_drag_overlay()
        self._aspect_box.set_overlay(self._text_drag_overlay)
        self._wire_preview_signals()
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)
        self._back_btn.setEnabled(True)
        self._fwd_btn.setEnabled(True)
        self._seek_slider.setEnabled(True)
        self._preview_title.setText("Preview")
        self._background_path = ""
        self._logo_path = ""
        self._mp3_path = ""
        if isinstance(self._last_preview_args, dict):
            self.set_renderer_preview(**self._last_preview_args)
        return self._preview_runtime_nonce

    def _wire_preview_signals(self) -> None:
        if self._preview is None:
            return
        self._preview.position_changed.connect(self.spectrum_position_changed.emit)
        self._preview.lightning_position_changed.connect(self.lightning_position_changed.emit)
        if hasattr(self._preview, "logo_position_changed"):
            self._preview.logo_position_changed.connect(self.logo_position_changed.emit)
        self._preview.background_transform_changed.connect(self.background_transform_changed.emit)
        self._preview.text_domain_position_changed.connect(self.text_domain_position_changed.emit)
        self._preview.playback_state_changed.connect(self._on_preview_playback_state)
        if hasattr(self._preview, "gl_failed"):
            self._preview.gl_failed.connect(self._on_preview_gl_failed)

    def _on_preview_gl_failed(self, message: str) -> None:
        """REQ-P1.2: keep stage usable; disable transport while GPU preview is down."""
        detail = str(message or "").strip()
        if detail:
            self._preview_title.setText("Preview (GPU failed)")
        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._back_btn.setEnabled(False)
        self._fwd_btn.setEnabled(False)
        self._seek_slider.setEnabled(False)

    def _wire_text_drag_overlay(self) -> None:
        if self._text_drag_overlay is None:
            return
        self._text_drag_overlay.drag_offset_changed.connect(self._on_text_drag_offset)
        self._text_drag_overlay.position_committed.connect(self._on_text_drag_committed)
        self._text_drag_overlay.box_resize_changed.connect(self._on_text_box_resize_changed)
        self._text_drag_overlay.box_resized.connect(self._on_text_box_resized)

    def _on_text_box_resize_changed(self, domain: str, patch: object) -> None:
        self.text_domain_box_resize_changed.emit(str(domain), patch if isinstance(patch, dict) else {})

    def _on_text_box_resized(self, domain: str, patch: object) -> None:
        self.text_domain_box_resized.emit(str(domain), patch if isinstance(patch, dict) else {})

    def _on_text_drag_offset(self, domain: str, dx: float, dy: float) -> None:
        """Forward live pixel offset into GPU paintGL — real-time text drag."""
        if self._preview is None:
            return
        self._preview.set_text_drag_offset(str(domain), float(dx), float(dy))

    def _on_text_drag_committed(self, domain: str, x: float, y: float) -> None:
        """Bake final coords into preview template, then sync draft."""
        if self._preview is not None:
            self._preview.apply_text_domain_position(str(domain), float(x), float(y))
        self.text_domain_position_changed.emit(str(domain), float(x), float(y))

    def set_preview_context(self, *, title: str, notes: list[str]) -> None:
        self._preview_title.setText(title or "Preview")
        if self._fallback is not None:
            detail = "\n".join(notes) if notes else ""
            self._fallback.setText(
                f"{title}\n\n{detail}\n\n{gpu_preview_install_hint()}".strip()
                if detail
                else gpu_preview_install_hint()
            )

    def set_preview_edit_modes(
        self,
        *,
        background: bool,
        spectrum_position: bool,
        text_domain: str = "",
        lightning_position: bool = False,
        logo_position: bool = False,
    ) -> None:
        domain = str(text_domain or "").strip().lower()
        self._active_text_domain = domain if domain in {"album", "title"} else ""
        if self._preview is not None:
            self._preview.set_edit_modes(
                background=background,
                spectrum_position=spectrum_position,
                text_domain=self._active_text_domain,
                lightning_position=lightning_position,
                logo_position=logo_position,
            )
        if self._text_drag_overlay is not None:
            self._text_drag_overlay.set_edit_domain(self._active_text_domain)

    def set_selected_lightning_layer_index(self, index: int) -> None:
        if self._preview is not None and hasattr(self._preview, "set_selected_lightning_layer_index"):
            self._preview.set_selected_lightning_layer_index(int(index))

    def set_selected_spectrum_instance_index(self, index: int) -> None:
        if self._preview is not None and hasattr(self._preview, "set_selected_spectrum_instance_index"):
            self._preview.set_selected_spectrum_instance_index(int(index))

    def bind_text_drag_overlay(
        self,
        *,
        domain: str,
        enabled: bool,
        lines: list[str],
        anchor: str,
        x: float,
        y: float,
        font_family: str,
        font_size: float,
        bold: bool,
        italic: bool,
        color: str,
        render_base_height: float = 450.0,
        box_width: float = 0.0,
        line_spacing: float = 1.2,
        letter_spacing: float = 0.0,
        content_width: float = 0.0,
        content_height: float = 0.0,
    ) -> None:
        """Sync transparent drag catcher with Album/Title draft (GPU draws the text)."""
        if self._text_drag_overlay is None:
            return
        self._text_drag_overlay.bind_text(
            domain=domain,
            enabled=enabled,
            lines=lines,
            anchor=anchor,
            x=x,
            y=y,
            font_family=font_family,
            font_size=font_size,
            bold=bold,
            italic=italic,
            color=color,
            render_base_height=render_base_height,
            box_width=box_width,
            line_spacing=line_spacing,
            letter_spacing=letter_spacing,
            content_width=content_width,
            content_height=content_height,
        )

    def bind_playback(self, playback: VideoPlaybackState | None) -> None:
        self._playback = playback or VideoPlaybackState()
        self._refresh_playback_ui()

    def set_current_track(self, track_path: str) -> None:
        """Show the active preview track name in the Playback section."""
        path = str(track_path or "").strip()
        self._current_track_path = path
        if self._track_label is None:
            return
        if not path:
            self._track_label.setText("No track selected")
            self._track_label.setToolTip("")
            return
        name = Path(path).name
        self._track_label.setText(f"Now playing: {name}")
        self._track_label.setToolTip(path)

    def sync_playback_transport(self, playback: VideoPlaybackState | None) -> None:
        """Update transport controls without reloading preview assets."""
        self._playback = playback or VideoPlaybackState()
        self._refresh_playback_ui()

    def _sync_playback_timer(self) -> None:
        if self._preview is None:
            self._playback_timer.stop()
            return
        if self._playback.is_playing:
            if not self._playback_timer.isActive():
                self._playback_timer.start()
        else:
            self._playback_timer.stop()

    def issue_playback_command(self, command: str) -> None:
        if self._preview is None:
            return
        normalized = str(command or "").strip().lower()
        if normalized == "play":
            self._preview.play_preview()
        elif normalized == "pause":
            self._preview.pause_preview()
        elif normalized == "stop":
            self._preview.stop_preview()

    def seek_preview(self, time_sec: float) -> None:
        if self._preview is None:
            return
        self._preview.seek_preview(time_sec)

    def _toggle_playback(self) -> None:
        if self._playback.is_playing:
            self.playback_command_requested.emit("pause")
        else:
            self.playback_command_requested.emit("play")

    def _on_seek_pressed(self) -> None:
        self._seek_dragging = True

    def _on_seek_released(self) -> None:
        self._seek_dragging = False
        if self._playback.duration_sec <= 0:
            return
        ratio = float(self._seek_slider.value()) / 1000.0
        target = float(self._playback.duration_sec) * ratio
        self.playback_seek_requested.emit(target)

    def _on_seek_changed(self, value: int) -> None:
        if not self._seek_dragging or self._playback.duration_sec <= 0:
            return
        ratio = float(value) / 1000.0
        current = float(self._playback.duration_sec) * ratio
        self._time_label.setText(
            f"{_format_time_label(current)} / {_format_time_label(self._playback.duration_sec)}"
        )

    def _on_preview_playback_state(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self.playback_state_changed.emit(payload)
        self._refresh_playback_ui_from_preview()

    def _refresh_playback_ui_from_preview(self) -> None:
        if self._preview is None:
            return
        snapshot = self._preview.playback_snapshot()
        self._playback = VideoPlaybackState(
            is_playing=bool(snapshot.get("isPlaying")),
            is_ready=bool(snapshot.get("isReady")),
            is_loading=bool(snapshot.get("isLoading")),
            current_time_sec=float(snapshot.get("currentTimeSec") or 0.0),
            duration_sec=float(snapshot.get("durationSec") or 0.0),
        )
        self._refresh_playback_ui()

    def _refresh_playback_ui(self) -> None:
        if self._preview is not None:
            snapshot = self._preview.playback_snapshot()
            self._playback = VideoPlaybackState(
                is_playing=bool(snapshot.get("isPlaying")),
                is_ready=bool(snapshot.get("isReady")),
                is_loading=bool(snapshot.get("isLoading")),
                current_time_sec=float(snapshot.get("currentTimeSec") or 0.0),
                duration_sec=float(snapshot.get("durationSec") or 0.0),
            )
        playback = self._playback
        duration = float(max(0.0, playback.duration_sec))
        current = float(max(0.0, playback.current_time_sec))
        if duration > 0 and not self._seek_dragging:
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(int(round((current / duration) * 1000)))
            self._seek_slider.blockSignals(False)
        self._time_label.setText(f"{_format_time_label(current)} / {_format_time_label(duration)}")
        self._play_btn.setText("Pause" if playback.is_playing else "Play")
        enabled = bool(playback.is_ready or playback.is_loading or playback.duration_sec > 0)
        self._play_btn.setEnabled(enabled)
        self._stop_btn.setEnabled(enabled)
        self._back_btn.setEnabled(duration > 0)
        self._fwd_btn.setEnabled(duration > 0)
        self._seek_slider.setEnabled(duration > 0)
        self._sync_playback_timer()

    def set_renderer_preview(
        self,
        *,
        template: dict,
        background_path: str,
        logo_path: str,
        mp3_path: str,
        aspect_width: int = 16,
        aspect_height: int = 9,
    ) -> None:
        self._last_preview_args = {
            "template": dict(template),
            "background_path": background_path,
            "logo_path": logo_path,
            "mp3_path": mp3_path,
            "aspect_width": aspect_width,
            "aspect_height": aspect_height,
        }
        if self._preview is None:
            return
        # Skip template push only while position-dragging (live offset owns paint).
        # During box resize we *want* template pushes so wrap/scale reflow live.
        position_dragging = bool(
            self._text_drag_overlay is not None and self._text_drag_overlay.is_position_dragging()
        )
        template_key = json.dumps(template, sort_keys=True, default=str)
        if template_key != self._last_template_key:
            self._last_template_key = template_key
            self._last_template = dict(template)
            # Only push when content actually changed (normalize+peak-cache clear is expensive).
            if self._preview is not None and not position_dragging:
                self._preview.set_template(template)
        background_path = _existing_file_path(background_path)
        logo_path = _existing_file_path(logo_path)
        mp3_path = _existing_file_path(mp3_path)
        if background_path != self._background_path:
            self._background_path = background_path
            self._preview.load_background(background_path)
        if logo_path != self._logo_path:
            self._logo_path = logo_path
            self._preview.load_logo(logo_path)
        if mp3_path != self._mp3_path:
            self._mp3_path = mp3_path
            if mp3_path:
                self._preview.load_audio(mp3_path)
            else:
                self._preview.stop_preview()
        if self._aspect_box is not None:
            self._aspect_box.set_ratio(max(1, aspect_width), max(1, aspect_height))

    def bind_output_resolution(self, resolution: str, *, pending: bool = False) -> None:
        self._resolution_pending = pending
        normalized = str(resolution or "").strip() or "1920x1080"
        index = self._resolution_combo.findData(normalized)
        if index < 0 and normalized not in OUTPUT_RESOLUTION_VALUES:
            self._resolution_combo.addItem(normalized, normalized)
            index = self._resolution_combo.findData(normalized)
        if index >= 0:
            blocked = self._resolution_combo.blockSignals(True)
            self._resolution_combo.setCurrentIndex(index)
            self._resolution_combo.blockSignals(blocked)
        self._resolution_combo.setEnabled(not pending)

    def _on_resolution_changed(self, _index: int) -> None:
        if self._resolution_pending:
            return
        value = str(self._resolution_combo.currentData() or "").strip()
        if value:
            self.output_resolution_changed.emit(value)
