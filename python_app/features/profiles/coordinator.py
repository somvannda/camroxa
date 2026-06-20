"""ProfileCoordinator — owns profile-level orchestration.

Uses dependency injection to avoid direct MainWindow references.
"""
from __future__ import annotations

from typing import Any, Callable

from ..ports import EventBusPort, LoggerPort


class ProfileCoordinator:
    """Owns profile-level orchestration extracted from MainWindow.

    All host dependencies are injected via constructor parameters so the
    coordinator is instantiable without a QApplication.
    """

    def __init__(
        self,
        *,
        refresh_list_fn: Callable[[], None],
        selected_profile_fn: Callable[[], dict[str, Any] | None],
        save_profile_fn: Callable[[], None],
        logger: LoggerPort | None = None,
    ) -> None:
        if refresh_list_fn is None:
            raise ValueError("ProfileCoordinator requires a non-None refresh_list_fn")
        if selected_profile_fn is None:
            raise ValueError("ProfileCoordinator requires a non-None selected_profile_fn")
        if save_profile_fn is None:
            raise ValueError("ProfileCoordinator requires a non-None save_profile_fn")
        self._refresh_list_fn = refresh_list_fn
        self._selected_profile_fn = selected_profile_fn
        self._save_profile_fn = save_profile_fn
        self._logger = logger

    def refresh_list(self) -> None:
        """Refresh the visible profile list in the UI."""
        return self._refresh_list_fn()

    def selected_profile(self) -> dict[str, Any] | None:
        """Return the currently selected normalized profile."""
        return self._selected_profile_fn()

    def save_profile(self) -> None:
        """Persist edits for the selected profile."""
        return self._save_profile_fn()
