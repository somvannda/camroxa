"""Studio preview stage — compiles composition and feeds GPU preview."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from features.studio.lib.scene_document import normalize_studio_document
from shared.themes.deep_blue import SUBTITLE_LABEL_ID

try:
    from visualizer.preview_widget import AspectRatioBox, VideoSpectrumPreview

    _GPU_OK = True
except Exception:  # pragma: no cover
    AspectRatioBox = None  # type: ignore[misc, assignment]
    VideoSpectrumPreview = None  # type: ignore[misc, assignment]
    _GPU_OK = False


def _existing_file(path: str | None) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    try:
        return text if Path(text).is_file() else ""
    except OSError:
        return ""


class StudioPreviewStage(QWidget):
    spectrum_position_changed = Signal(int, int)
    logo_position_changed = Signal(int, int)
    spectrum_size_delta_requested = Signal(float)
    playback_state_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview: Any = None
        self._background_path = ""
        self._background_video_path = ""
        self._logo_path = ""
        self._audio_path = ""
        self._status = QLabel("Preview")
        self._status.setObjectName(SUBTITLE_LABEL_ID)
        self._status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._status)

        if _GPU_OK and VideoSpectrumPreview is not None and AspectRatioBox is not None:
            self._preview = VideoSpectrumPreview()
            try:
                self._preview.setMinimumHeight(120)
                self._preview.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Expanding,
                )
            except Exception:
                pass
            if hasattr(self._preview, "position_changed"):
                self._preview.position_changed.connect(self.spectrum_position_changed.emit)
            if hasattr(self._preview, "logo_position_changed"):
                self._preview.logo_position_changed.connect(self.logo_position_changed.emit)
            if hasattr(self._preview, "spectrum_size_delta_requested"):
                self._preview.spectrum_size_delta_requested.connect(
                    self.spectrum_size_delta_requested.emit
                )
            if hasattr(self._preview, "playback_state_changed"):
                self._preview.playback_state_changed.connect(self.playback_state_changed.emit)
            box = AspectRatioBox(
                self._preview,
                ratio_w=16,
                ratio_h=9,
                enforce_height_for_width=False,
            )
            box.setMinimumHeight(120)
            box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout.addWidget(box, stretch=1)
        else:
            fallback = QLabel(
                "GPU preview unavailable in this environment.\n"
                "Scene still compiles — open Studio on a GPU-ready desktop build for live pixels."
            )
            fallback.setObjectName(SUBTITLE_LABEL_ID)
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setWordWrap(True)
            layout.addWidget(fallback, stretch=1)

    @property
    def preview_widget(self) -> Any:
        return self._preview

    def apply_document(self, doc: dict[str, Any]) -> None:
        from visualizer.composition_renderer import document_to_renderer_dict

        scene = normalize_studio_document(doc)
        try:
            rendered = document_to_renderer_dict(scene)
        except Exception as exc:
            self._status.setText(f"Compile failed: {exc}")
            return

        engine = rendered.get("engine") if isinstance(rendered.get("engine"), dict) else {}
        shape = (engine.get("spectrum") or {}).get("shape") if isinstance(engine.get("spectrum"), dict) else None
        lighting = engine.get("lighting")
        camera = engine.get("camera")
        atmosphere = engine.get("atmosphere")
        assets = scene.get("assets") if isinstance(scene.get("assets"), dict) else {}
        bg = _existing_file(str(assets.get("backgroundImage") or ""))
        bg_video = _existing_file(str(assets.get("backgroundVideo") or ""))
        logo = _existing_file(str(assets.get("logo") or ""))
        audio = _existing_file(str(assets.get("audio") or ""))
        plate = "video" if bg_video else ("image" if bg else "no")
        self._status.setText(
            f"Compiled · spectrum={shape or 'none'} · lighting={lighting or 'none'} · "
            f"camera={camera or 'none'} · atmosphere={atmosphere or 'none'} · "
            f"post={engine.get('postCount', 0)} · "
            f"bg={plate} · logo={'yes' if logo else 'no'} · audio={'yes' if audio else 'no'}"
        )
        if self._preview is None:
            return
        try:
            self._preview.set_template(rendered)
            if bg_video != self._background_video_path or bg != self._background_path:
                self._background_video_path = bg_video
                self._background_path = bg
                if bg_video and hasattr(self._preview, "load_background_video"):
                    self._preview.load_background_video(bg_video)
                else:
                    if hasattr(self._preview, "clear_background_video"):
                        self._preview.clear_background_video()
                    self._preview.load_background(bg)
            if logo != self._logo_path:
                self._logo_path = logo
                self._preview.load_logo(logo)
            if audio != self._audio_path:
                self._audio_path = audio
                if audio:
                    self._preview.load_audio(audio)
                else:
                    self._preview.stop_preview()
        except Exception as exc:
            self._status.setText(f"Preview update failed: {exc}")

    def seek(self, time_sec: float) -> None:
        if self._preview is not None and hasattr(self._preview, "seek_preview"):
            self._preview.seek_preview(float(time_sec))

    def set_playing(self, playing: bool) -> None:
        if self._preview is None:
            return
        if playing and hasattr(self._preview, "play_preview"):
            try:
                self._preview.play_preview()
                return
            except Exception:
                pass
        if not playing and hasattr(self._preview, "pause_preview"):
            try:
                self._preview.pause_preview()
                return
            except Exception:
                pass
        if playing and hasattr(self._preview, "start_preview"):
            self._preview.start_preview()
        elif not playing and hasattr(self._preview, "stop_preview"):
            if hasattr(self._preview, "pause"):
                self._preview.pause()

    def set_loop_playback(self, enabled: bool) -> None:
        if self._preview is not None and hasattr(self._preview, "set_loop_playback"):
            try:
                self._preview.set_loop_playback(bool(enabled))
            except Exception:
                pass

    def is_playing(self) -> bool:
        if self._preview is None:
            return False
        try:
            if hasattr(self._preview, "playback_snapshot"):
                snap = self._preview.playback_snapshot()
                if isinstance(snap, dict):
                    return bool(snap.get("isPlaying"))
            return bool(getattr(self._preview, "audio_playing", False))
        except Exception:
            return False

    def duration_sec(self) -> float:
        if self._preview is None:
            return 0.0
        for attr in ("duration", "audio_duration", "total_duration"):
            if hasattr(self._preview, attr):
                try:
                    return float(getattr(self._preview, attr) or 0.0)
                except Exception:
                    pass
        try:
            snap = self._preview.snapshot_state() if hasattr(self._preview, "snapshot_state") else {}
            if isinstance(snap, dict):
                return float(snap.get("durationSec") or snap.get("duration") or 0.0)
        except Exception:
            pass
        return 0.0

    def position_sec(self) -> float:
        if self._preview is None:
            return 0.0
        try:
            return float(getattr(self._preview, "current_time", 0.0) or 0.0)
        except Exception:
            return 0.0

    def set_interaction_modes(
        self,
        *,
        spectrum_position: bool = False,
        logo_position: bool = False,
    ) -> None:
        if self._preview is None:
            return
        if hasattr(self._preview, "set_interaction_modes"):
            self._preview.set_interaction_modes(
                spectrum_position=bool(spectrum_position),
                logo_position=bool(logo_position),
            )
            return
        if hasattr(self._preview, "set_spectrum_position_edit_mode"):
            self._preview.set_spectrum_position_edit_mode(bool(spectrum_position))
        if hasattr(self._preview, "set_logo_position_edit_mode"):
            self._preview.set_logo_position_edit_mode(bool(logo_position))
