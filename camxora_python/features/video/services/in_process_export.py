"""In-process GPU export from warm preview session (REQ-2.2)."""

from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable

from features.video.services.export_job import ExportSettings
from features.video.lib.render_scene_request import ManualRenderSceneRequest
from visualizer_video.gpu_render import GpuOptions

ExportEventHandler = Callable[[dict], None]


def in_process_export_enabled() -> bool:
    """Return True when warm preview GL export is allowed (REQ-2.6).

    Set ``CAMXORA_INPROCESS_EXPORT=1`` (or ``true``/``yes``/``on``) to route manual
    export through the preview OpenGL context instead of daemon/subprocess. Default is
    off (``0``) until golden-frame parity is verified (REQ-2.7).
    """
    raw = str(os.environ.get("CAMXORA_INPROCESS_EXPORT", "0") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize_template(template: dict | None) -> dict:
    from features.video.lib.preview_export_parity import canonicalize_renderer_template

    return canonicalize_renderer_template(template)


def preview_matches_export(
    preview: Any | None,
    *,
    mp3_path: str,
    template: dict,
    background_path: str,
    logo_path: str,
) -> bool:
    if preview is None or not bool(getattr(preview, "_gl_ready", False)):
        return False
    if str(getattr(preview, "audio_path", "") or "").strip().lower() != str(mp3_path or "").strip().lower():
        return False
    if str(getattr(preview, "bg_path", "") or "").strip().lower() != str(background_path or "").strip().lower():
        return False
    if str(getattr(preview, "logo_path", "") or "").strip().lower() != str(logo_path or "").strip().lower():
        return False
    if bool(getattr(preview, "analysis_loading", False)):
        return False
    if getattr(preview, "analyzer", None) is None:
        return False
    from features.video.lib.preview_export_parity import templates_match

    return templates_match(getattr(preview, "template", None), template)


def resolve_manual_export_backend(
    preview: Any | None,
    *,
    scene: ManualRenderSceneRequest,
    background_path: str,
    logo_path: str,
    mp3_path: str,
) -> str:
    if not in_process_export_enabled():
        return "subprocess"
    if preview_matches_export(
        preview,
        mp3_path=mp3_path,
        template=scene.template,
        background_path=background_path,
        logo_path=logo_path,
    ):
        return "in-process"
    return "subprocess"


def build_gpu_options(
    *,
    scene: ManualRenderSceneRequest,
    export_settings: ExportSettings,
    speed_mode: str,
) -> GpuOptions:
    tpl_b64 = base64.b64encode(
        json.dumps(scene.template, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    return GpuOptions(
        mp3_path=str(scene.assets.audio_path or ""),
        background_path=str(scene.assets.background_path or ""),
        output_dir=str(export_settings.output_dir),
        template_path="unused_template.json",
        template_b64=tpl_b64,
        logo_path=str(scene.assets.logo_path or ""),
        ffmpeg_path=str(export_settings.ffmpeg_path),
        fps=int(scene.output.fps),
        width=int(scene.output.width),
        height=int(scene.output.height),
        speed_mode=str(speed_mode or "balanced"),
        output_path=str(export_settings.output_path or ""),
    )


@dataclass
class InProcessExportSession:
    preview: Any
    opts: GpuOptions
    on_event: ExportEventHandler | None
    analyzer: Any | None = None

    def __post_init__(self) -> None:
        self._cancel = threading.Event()
        self._cancel_hooks: dict[str, Any] = {}

    def cancel(self) -> None:
        self._cancel.set()
        pipe_writer = self._cancel_hooks.get("pipe_writer")
        if pipe_writer is not None:
            try:
                pipe_writer.cancel()
            except Exception:
                pass

    def run(self) -> int:
        from PySide6.QtGui import QOpenGLContext
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            raise RuntimeError("QApplication is required for in-process export")

        prepare_surface = getattr(self.preview, "blocking_prepare_export_surface", None)
        if not callable(prepare_surface):
            raise RuntimeError("Preview widget does not support in-process export GL setup")

        self._set_preview_overlay(True, "Exporting…")
        surface = prepare_surface()

        # Context must be created + makeCurrent on THIS (worker) thread.
        # Surface must be created on the GUI thread (Qt requirement).
        export_gl = QOpenGLContext()
        export_gl.setFormat(surface.format())
        if not export_gl.create():
            self._set_preview_overlay(False, "")
            raise RuntimeError("Failed to create export OpenGL context")
        if not export_gl.makeCurrent(surface):
            self._set_preview_overlay(False, "")
            raise RuntimeError("Failed to make export OpenGL context current")

        from visualizer_video.preview_widget import _QtGLContextLoader

        import moderngl
        from visualizer_video.gpu_render import run_gpu_render

        def _ctx_factory() -> moderngl.Context:
            moderngl.init_context(loader=_QtGLContextLoader(export_gl))
            ctx = moderngl.get_context()
            ctx.enable(moderngl.BLEND)
            ctx.enable(moderngl.PROGRAM_POINT_SIZE)
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)
            return ctx

        try:
            return int(
                run_gpu_render(
                    self.opts,
                    on_event=self._on_event_with_backend,
                    existing_analyzer=self.analyzer,
                    ctx_factory=_ctx_factory,
                    cancel_check=self._cancel.is_set,
                    cancel_hooks=self._cancel_hooks,
                )
            )
        finally:
            try:
                export_gl.doneCurrent()
            except Exception:
                pass
            self._set_preview_overlay(False, "")

    def _on_event_with_backend(self, event: dict) -> None:
        payload = dict(event)
        payload.setdefault("backend", "in-process")
        if self.on_event is not None:
            self.on_event(payload)

    def _set_preview_overlay(self, active: bool, message: str) -> None:
        setter = getattr(self.preview, "invoke_set_export_overlay", None)
        if callable(setter):
            try:
                setter(bool(active), str(message or ""))
            except Exception:
                pass
