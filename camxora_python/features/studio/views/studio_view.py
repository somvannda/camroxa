"""Composition Studio page — docs-first platform workspace (P0–P7 slices)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox, QVBoxLayout, QWidget

from features.studio.lib.scene_document import (
    apply_axis_patch,
    inspector_bind_state,
    normalize_studio_document,
)
from features.studio.lib.schema_validate import validate_composition_document
from features.studio.plugins.loader import discover_plugins
from features.studio.services.ai_designer import AiDesignerEngine
from features.studio.services.marketplace_cloud import MarketplaceCloudService
from features.studio.services.studio_export import (
    build_studio_manual_export_request,
    export_project_json,
    studio_export_options,
    studio_export_readiness,
)
from shared.lib.export_codec import normalize_export_speed_mode
from features.studio.services.studio_store import StudioStore
from features.studio.services.template_library import StudioTemplateLibrary
from features.studio.widgets.studio_shell import StudioShell
from features.video.workers.manual_export_worker import ManualExportRequest, VideoManualExportWorker
from shared.services.action_feedback import notify_action
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache
from shared.themes.deep_blue import VIDEO_WORKSPACE_ID
from visualizer.scene import NONE


class StudioView(QWidget):
    """Greenfield Studio page. Does not import Video inspectors or draft hydrate."""

    def __init__(
        self,
        api: PlatformApi,
        parent: QWidget | None = None,
        *,
        cache: WorkspaceCache | None = None,
    ) -> None:
        super().__init__(parent)
        # Share Video workspace QSS (account_card rails / stage chrome).
        self.setObjectName(VIDEO_WORKSPACE_ID)
        self._api = api
        self._cache = cache
        self._store = StudioStore()
        self._templates = StudioTemplateLibrary()
        self._ai = AiDesignerEngine()
        self._marketplace = MarketplaceCloudService()
        self._document: dict[str, Any] = {}
        self._undo_stack: list[dict[str, Any]] = []
        self._dirty = False
        self._export_worker: VideoManualExportWorker | None = None
        self._favorites: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._shell = StudioShell()
        layout.addWidget(self._shell)

        self._shell.new_requested.connect(self._on_new)
        self._shell.save_requested.connect(self._on_save)
        self._shell.undo_requested.connect(self._on_undo)
        self._shell.project_selected.connect(self._on_project_selected)
        self._shell.name_changed.connect(self._on_name_changed)
        self._shell.patch_requested.connect(self._on_patch)
        self._shell.export_json_requested.connect(self._on_export_json)
        self._shell.export_video_requested.connect(self._on_export_video)
        self._shell.export_options_changed.connect(self._on_export_options)
        self._shell.select_audio_requested.connect(self._on_select_audio)
        self._shell.add_tracks_requested.connect(self._on_add_tracks)
        self._shell.track_selected.connect(self._on_track_selected)
        self._shell.remove_track_requested.connect(self._on_remove_track)
        self._shell.template_save_requested.connect(self._on_save_template)
        self._shell.ai_generate_requested.connect(self._on_ai_generate)
        self._shell.ai_modify_requested.connect(self._on_ai_modify)
        self._shell.ai_improve_requested.connect(self._on_ai_improve)
        self._shell.json_apply_requested.connect(self._on_json_apply)
        self._shell.timeline_play_toggled.connect(self._on_timeline_play)
        self._shell.timeline_stop_requested.connect(self._on_timeline_stop)
        self._shell.timeline_seek_requested.connect(self._on_timeline_seek)
        self._shell.timeline_seek_relative_requested.connect(self._on_timeline_seek_relative)
        self._shell.favorite_toggled.connect(self._on_favorite)
        self._shell.node_selected.connect(self._on_node_selected)
        self._shell.spectrum_position_changed.connect(self._on_spectrum_position)
        self._shell.logo_position_changed.connect(self._on_logo_position)
        self._shell.spectrum_size_delta_requested.connect(self._on_spectrum_size_delta)

        self._autosave = QTimer(self)
        self._autosave.setInterval(15000)
        self._autosave.timeout.connect(self._autosave_tick)
        self._autosave.start()

        self._tick = QTimer(self)
        self._tick.setInterval(200)
        self._tick.timeout.connect(self._sync_timeline)
        self._tick.start()

        self._discover_plugins()
        self._load_active()
        self._on_node_selected(self._shell._left._tree.current_node())

    def activate_page(self) -> None:
        self._refresh_project_list()
        self._push_ui()
        self._on_node_selected(self._shell._left._tree.current_node())

    def deactivate_page(self) -> None:
        if self._dirty:
            self._on_save()

    def _discover_plugins(self) -> None:
        plugins_root = Path(__file__).resolve().parents[1] / "plugins"
        # Ensure sample plugin is discoverable beside package.
        discover_plugins(plugins_root)

    def _load_favorites(self) -> None:
        prefs = self._store.read_prefs()
        fav = prefs.get("favoriteAssets")
        self._favorites = [str(x) for x in fav] if isinstance(fav, list) else []
        self._shell.set_favorites(self._favorites)

    def _load_active(self) -> None:
        self._document = self._store.load_active_or_create()
        self._undo_stack.clear()
        self._dirty = False
        self._load_favorites()
        self._refresh_project_list()
        self._push_ui()

    def _refresh_project_list(self) -> None:
        projects = self._store.list_projects()
        selected = str(self._document.get("id") or "") or None
        self._shell.set_projects(projects, selected)

    def _push_ui(self) -> None:
        doc = normalize_studio_document(self._document)
        self._shell.set_name(str(doc.get("name") or "Untitled Composition"))
        self._shell.set_dirty(self._dirty)
        self._shell.bind_document(inspector_bind_state(doc))
        ready, reason = studio_export_readiness(doc)
        self._shell.set_export_readiness(ready, reason)
        self._shell.apply_preview(doc)
        self._sync_preview_interaction()

    def _sync_preview_interaction(self) -> None:
        """Spectrum drag stays on whenever spectrum is active — not only when selected."""
        doc = normalize_studio_document(self._document)
        comp = doc.get("composition") if isinstance(doc.get("composition"), dict) else {}
        spec = comp.get("spectrum") if isinstance(comp.get("spectrum"), dict) else {}
        shape = str(spec.get("shape") or NONE)
        spectrum_on = shape not in (None, "", NONE, "none")
        key = ""
        try:
            key = str(self._shell._left._tree.current_node() or "")
        except Exception:
            key = ""
        attached = bool(doc.get("spectrumAttachToLogo", False))
        has_center = bool(str((doc.get("assets") or {}).get("logo") or "").strip())
        # Center image is authored under Spectrum (Vizzy-style); drag when attached.
        center_drag = key == "spectrum" and (attached or has_center)
        self._shell.set_preview_interaction_modes(
            spectrum_position=spectrum_on,
            logo_position=center_drag,
        )

    def _on_export_options(self, options: dict) -> None:
        if not options:
            return
        current = studio_export_options(self._document)
        if (
            current.get("resolution") == options.get("resolution")
            and int(current.get("fps") or 24) == int(options.get("fps") or 24)
            and current.get("quality") == options.get("quality")
            and bool(current.get("includeAudio", True)) == bool(options.get("includeAudio", True))
            and float(current.get("rangeStart") or 0.0) == float(options.get("rangeStart") or 0.0)
            and float(current.get("rangeEnd") or 0.0) == float(options.get("rangeEnd") or 0.0)
        ):
            return
        self._checkpoint()
        self._document = apply_axis_patch(self._document, {"studioExport": options})
        self._dirty = True
        self._push_ui()

    def _checkpoint(self) -> None:
        self._undo_stack.append(deepcopy(self._document))
        if len(self._undo_stack) > 40:
            self._undo_stack = self._undo_stack[-40:]

    def _on_patch(self, patch: dict) -> None:
        if not patch:
            return
        self._checkpoint()
        self._document = apply_axis_patch(self._document, patch)
        self._dirty = True
        self._push_ui()

    def _on_node_selected(self, key: str) -> None:
        _ = key
        self._sync_preview_interaction()

    def _on_spectrum_position(self, x: int, y: int) -> None:
        # Preview already moved live; persist without full UI rebuild mid-drag.
        self._document = apply_axis_patch(
            self._document,
            {"compositionSpectrumPositionPx": {"x": float(x), "y": float(y)}},
        )
        self._dirty = True
        self._shell.set_dirty(True)

    def _on_logo_position(self, x: int, y: int) -> None:
        patch: dict[str, Any] = {
            "compositionLogoOffsetX": max(-0.5, min(0.5, float(x) / 480.0)),
            "compositionLogoOffsetY": max(-0.5, min(0.5, float(y) / 270.0)),
        }
        doc = normalize_studio_document(self._document)
        if bool(doc.get("spectrumAttachToLogo", False)):
            patch["compositionSpectrumPositionPx"] = {"x": float(x), "y": float(y)}
        self._document = apply_axis_patch(self._document, patch)
        self._dirty = True
        self._shell.set_dirty(True)

    def _on_spectrum_size_delta(self, delta: float) -> None:
        state = inspector_bind_state(self._document)
        try:
            cur = float(state.get("compositionSpectrumSizeScale") or 1.0)
        except (TypeError, ValueError):
            cur = 1.0
        nxt = max(0.35, min(2.5, cur + float(delta)))
        if abs(nxt - cur) < 1e-6:
            return
        self._document = apply_axis_patch(
            self._document, {"compositionSpectrumSizeScale": nxt}
        )
        self._dirty = True
        # Size needs recompile so radius updates; keep it light (preview only).
        self._shell.apply_preview(self._document)
        self._shell.set_dirty(True)
        self._shell.bind_document(inspector_bind_state(self._document))

    def _on_name_changed(self, name: str) -> None:
        if str(self._document.get("name") or "") == name:
            return
        self._checkpoint()
        self._document = apply_axis_patch(self._document, {"name": name})
        self._dirty = True
        self._shell.set_dirty(True)

    def _on_new(self) -> None:
        self._checkpoint()
        self._document = self._store.create_project(name="Untitled Composition")
        self._dirty = False
        self._refresh_project_list()
        self._push_ui()

    def _on_save(self) -> None:
        errors = validate_composition_document(self._document)
        if errors:
            notify_action("Save blocked: " + "; ".join(errors[:3]), tone="error")
            return
        self._document = self._store.save_project(self._document)
        self._dirty = False
        self._refresh_project_list()
        self._push_ui()
        notify_action("Studio project saved.", tone="success")

    def _autosave_tick(self) -> None:
        if not self._dirty:
            return
        try:
            self._document = self._store.save_project(self._document)
            self._dirty = False
            self._shell.set_status("Autosaved")
            self._shell.set_dirty(False)
        except Exception:
            pass

    def _on_undo(self) -> None:
        if not self._undo_stack:
            return
        self._document = self._undo_stack.pop()
        self._dirty = True
        self._push_ui()

    def _on_project_selected(self, project_id: str) -> None:
        if project_id == str(self._document.get("id") or ""):
            return
        loaded = self._store.load_project(project_id)
        if loaded is None:
            return
        self._store.set_active_project_id(project_id)
        self._document = loaded
        self._undo_stack.clear()
        self._dirty = False
        self._push_ui()

    def _on_select_audio(self) -> None:
        self._on_add_tracks()

    def _on_add_tracks(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add audio tracks", "", "Audio (*.mp3 *.wav *.m4a *.flac)"
        )
        if not paths:
            return
        assets = self._document.get("assets") if isinstance(self._document.get("assets"), dict) else {}
        tracks = [str(x) for x in (assets.get("audioTracks") or []) if str(x).strip()]
        for path in paths:
            if path and path not in tracks:
                tracks.append(path)
        active = str(paths[0] if paths else assets.get("audio") or "")
        self._on_patch({"audioTracks": tracks, "audioPath": active})

    def _on_track_selected(self, path: str) -> None:
        track = str(path or "").strip()
        if not track:
            return
        if track == str((self._document.get("assets") or {}).get("audio") or ""):
            return
        self._on_patch({"audioPath": track})

    def _on_remove_track(self, path: str) -> None:
        track = str(path or "").strip()
        if track:
            self._on_patch({"removeAudioTrack": track})

    def _on_save_template(self) -> None:
        payload = self._templates.save_template(self._document)
        notify_action(f"Template saved: {payload.get('name')}", tone="success")

    def _on_ai_generate(self, prompt: str) -> None:
        if not str(prompt or "").strip():
            notify_action("Enter a prompt first.", tone="error")
            return
        self._checkpoint()
        result = self._ai.generate(prompt, base=self._document)
        self._document = result.document
        self._dirty = True
        self._shell.set_ai_explanation(result.explanation)
        self._push_ui()
        notify_action("AI generated scene JSON.", tone="success")

    def _on_ai_modify(self, prompt: str) -> None:
        if not str(prompt or "").strip():
            notify_action("Enter a modify prompt.", tone="error")
            return
        self._checkpoint()
        result = self._ai.modify(prompt, self._document)
        self._document = result.document
        self._dirty = True
        self._shell.set_ai_explanation(result.explanation)
        self._push_ui()

    def _on_ai_improve(self) -> None:
        self._checkpoint()
        result = self._ai.improve(self._document)
        self._document = result.document
        self._dirty = True
        self._shell.set_ai_explanation(result.explanation)
        self._push_ui()

    def _on_json_apply(self, data: dict) -> None:
        errors = validate_composition_document(data)
        if errors:
            notify_action("JSON invalid: " + "; ".join(errors[:3]), tone="error")
            return
        self._checkpoint()
        self._document = normalize_studio_document(data)
        self._dirty = True
        self._push_ui()

    def _on_favorite(self, asset_id: str, is_fav: bool) -> None:
        if is_fav and asset_id not in self._favorites:
            self._favorites.append(asset_id)
        if not is_fav and asset_id in self._favorites:
            self._favorites = [x for x in self._favorites if x != asset_id]
        prefs = self._store.read_prefs()
        prefs["favoriteAssets"] = self._favorites
        self._store.write_prefs(prefs)
        self._shell.set_favorites(self._favorites)

    def _on_timeline_play(self, playing: bool) -> None:
        self._shell.preview().set_playing(playing)
        self._shell.set_timeline_playing(playing)

    def _on_timeline_stop(self) -> None:
        preview = self._shell.preview()
        preview.set_playing(False)
        if hasattr(preview, "preview_widget") and preview.preview_widget is not None:
            widget = preview.preview_widget
            if hasattr(widget, "stop_preview"):
                try:
                    widget.stop_preview()
                except Exception:
                    pass
        preview.seek(0.0)
        self._shell.set_timeline_playing(False)
        self._shell.set_timeline_position(0.0)

    def _on_timeline_seek(self, time_sec: float) -> None:
        self._shell.preview().seek(time_sec)

    def _on_timeline_seek_relative(self, delta_sec: float) -> None:
        preview = self._shell.preview()
        duration = float(preview.duration_sec() or 0.0)
        if duration <= 0:
            return
        target = float(preview.position_sec() or 0.0) + float(delta_sec)
        preview.seek(max(0.0, min(duration, target)))

    def _sync_timeline(self) -> None:
        preview = self._shell.preview()
        dur = preview.duration_sec()
        if dur > 0:
            self._shell.set_timeline_duration(dur)
        self._shell.set_timeline_position(preview.position_sec())

    def _on_export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Studio project JSON",
            f"{self._document.get('name') or 'composition'}.project.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            out = export_project_json(self._document, path)
        except Exception as exc:
            notify_action(f"JSON export failed: {exc}", tone="error")
            return
        notify_action(f"Exported project JSON: {out.name}", tone="success")

    def _on_export_video(self) -> None:
        if self._export_worker is not None:
            return
        ok, reason = studio_export_readiness(self._document)
        if not ok:
            QMessageBox.warning(self, "Export Video", reason)
            return
        # Optional: enqueue cloud stub for P7 visibility
        pid = str(self._document.get("id") or "studio")
        cloud_job = self._marketplace.enqueue_cloud_render(project_id=pid)
        output_dir = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not output_dir:
            return
        opts = studio_export_options(self._document)
        try:
            scene = build_studio_manual_export_request(
                self._document,
                resolution=str(opts["resolution"]),
                fps=int(opts["fps"]),
                quality=str(opts["quality"]),
                output_dir=output_dir,
            )
        except Exception as exc:
            notify_action(f"Could not build export request: {exc}", tone="error")
            return
        request = ManualExportRequest(
            scene=scene,
            settings={
                "includeAudio": bool(opts["includeAudio"]),
                "rangeStart": float(opts["rangeStart"]),
                "rangeEnd": float(opts["rangeEnd"]),
                "studioExport": dict(opts),
            },
            speed_mode=normalize_export_speed_mode(opts["quality"]),
            output_dir=output_dir,
        )
        worker = VideoManualExportWorker(request)
        self._export_worker = worker
        self._shell.set_export_busy(True)
        self._shell.set_status(f"Exporting… (cloud stub {cloud_job.status})")
        worker.succeeded.connect(self._on_export_succeeded)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_finished)
        worker.start()

    def _on_export_succeeded(self, path: str) -> None:
        notify_action(f"Studio export complete: {path}", tone="success")
        self._shell.set_status("Export complete")

    def _on_export_failed(self, message: str) -> None:
        notify_action(message or "Studio export failed.", tone="error")
        self._shell.set_status("Export failed")

    def _on_export_finished(self) -> None:
        worker = self._export_worker
        self._export_worker = None
        self._shell.set_export_busy(False)
        if worker is not None:
            worker.deleteLater()
