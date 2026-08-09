"""Composition Studio page — docs-first, independent of Video workspace."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtWidgets import QFileDialog, QMessageBox, QVBoxLayout, QWidget

from features.studio.lib.scene_document import (
    apply_axis_patch,
    inspector_bind_state,
    normalize_studio_document,
)
from features.studio.services.studio_export import (
    build_studio_manual_export_request,
    export_project_json,
    studio_export_readiness,
)
from features.studio.services.studio_store import StudioStore
from features.studio.widgets.studio_shell import StudioShell
from features.video.workers.manual_export_worker import ManualExportRequest, VideoManualExportWorker
from shared.services.action_feedback import notify_action
from shared.services.platform_api import PlatformApi
from shared.services.workspace_cache import WorkspaceCache


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
        self.setObjectName("studio_workspace")
        self._api = api
        self._cache = cache
        self._store = StudioStore()
        self._document: dict[str, Any] = {}
        self._undo_stack: list[dict[str, Any]] = []
        self._dirty = False
        self._export_worker: VideoManualExportWorker | None = None

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
        self._shell.select_audio_requested.connect(self._on_select_audio)

        self._load_active()

    def activate_page(self) -> None:
        self._refresh_project_list()
        self._push_ui()

    def deactivate_page(self) -> None:
        return

    def _load_active(self) -> None:
        self._document = self._store.load_active_or_create()
        self._undo_stack.clear()
        self._dirty = False
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
        self._shell.apply_preview(doc)

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
        self._document = self._store.save_project(self._document)
        self._dirty = False
        self._refresh_project_list()
        self._push_ui()
        notify_action("Studio project saved.", tone="success")

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
        path, _ = QFileDialog.getOpenFileName(
            self, "Select audio track", "", "Audio (*.mp3 *.wav *.m4a *.flac)"
        )
        if path:
            self._on_patch({"audioPath": path})

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
        output_dir = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if not output_dir:
            return
        try:
            scene = build_studio_manual_export_request(self._document, output_dir=output_dir)
        except Exception as exc:
            notify_action(f"Could not build export request: {exc}", tone="error")
            return
        request = ManualExportRequest(scene=scene, settings={}, output_dir=output_dir)
        worker = VideoManualExportWorker(request)
        self._export_worker = worker
        self._shell.set_export_busy(True)
        self._shell.set_status("Exporting…")
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
