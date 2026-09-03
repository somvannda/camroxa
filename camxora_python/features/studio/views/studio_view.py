"""Studio shell page — embeds the ported Camxora Studio editor (features/studio UI).

The editor's own QSS is applied scoped to this page container so it never leaks
into the rest of the camxora_python shell. Playback is paused when the user
navigates away so no timers/workers keep running while the page is hidden.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from studio.app.theme import build_qss
from studio.core.project_state import ProjectState
from studio.ui.main_window import MainWindow


class StudioView(QWidget):
    """Shell page that hosts the full Camxora Studio timeline editor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("studio_page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._editor = MainWindow(ProjectState())
        layout.addWidget(self._editor)

        # Scope the studio theme to this page only (M1 keeps studio look; M2
        # realigns it to the camxora_python design system).
        self.setStyleSheet(build_qss())

    def activate_page(self) -> None:
        """Shell lifecycle hook — nothing needed on entry (editor is idle)."""
        return None

    def deactivate_page(self) -> None:
        """Shell lifecycle hook — pause playback and stop preview work."""
        controller = getattr(self._editor, "playback_controller", None)
        if controller is not None:
            try:
                controller.set_playing(False)
            except Exception:
                pass
