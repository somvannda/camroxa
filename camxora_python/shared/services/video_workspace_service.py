"""Video workspace state provider for workflow runtime overlay."""

from __future__ import annotations

import threading

from shared.models.desktop import VideoExportState, VideoWorkspaceState

_lock = threading.Lock()
_state: VideoWorkspaceState | None = None
_service: VideoWorkspaceService | None = None


class VideoWorkspaceService:
    """Returns current local video export workspace state."""

    def get_workspace_state(self) -> VideoWorkspaceState | None:
        with _lock:
            return _state

    def set_workspace_state(self, state: VideoWorkspaceState | None) -> None:
        global _state
        with _lock:
            _state = state

    def export_is_active(self) -> bool:
        state = self.get_workspace_state()
        if state is None:
            return False
        export = state.export
        return bool(export.running or export.merge_running)


def get_video_workspace_service() -> VideoWorkspaceService:
    global _service
    if _service is None:
        _service = VideoWorkspaceService()
    return _service


def build_empty_workspace() -> VideoWorkspaceState:
    return VideoWorkspaceState(export=VideoExportState())
