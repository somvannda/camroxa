"""VideoWorkspaceCoordinator — orchestrates video workspace state.

Coordinates template application, preview configuration, and export
handoff between the template and export coordinators.
"""

from __future__ import annotations

from typing import Any, Callable

from ..ports import EventBusPort


class VideoWorkspaceCoordinator:
    """Facade coordinating video workspace operations.

    Uses constructor injection for all dependencies, enabling unit
    testing without Qt and enforcing loose coupling between layers.
    """

    def __init__(
        self,
        template_coordinator: Any,
        export_coordinator: Any,
        bus: EventBusPort,
        settings_accessor: Callable[[], dict],
    ) -> None:
        if bus is None:
            raise ValueError("VideoWorkspaceCoordinator requires a non-None bus dependency")
        self._template_coordinator = template_coordinator
        self._export_coordinator = export_coordinator
        self._bus = bus
        self._settings_accessor = settings_accessor

    def apply_template_to_state(self, template: dict) -> dict:
        """Apply a video template to the current workspace state."""
        return {}

    def resolve_preview_config(self) -> dict:
        """Resolve the current preview configuration from workspace state."""
        return {}

    def prepare_export_handoff(self) -> dict:
        """Prepare workspace state for handoff to the export coordinator."""
        return {}

    def update_resolution(self, width: int, height: int) -> None:
        """Update the video resolution in workspace state."""
        pass

    def update_background(self, path: str) -> None:
        """Update the background image path in workspace state."""
        pass

    def update_logo(self, path: str) -> None:
        """Update the logo image path in workspace state."""
        pass
