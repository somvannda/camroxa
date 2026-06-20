"""VideoTemplateCoordinator — owns video-template orchestration.

Uses dependency injection to avoid direct MainWindow references.
"""
from __future__ import annotations

from typing import Callable

from ..ports import LoggerPort


class VideoTemplateCoordinator:
    """Owns video-template orchestration extracted from MainWindow.

    All host dependencies are injected via constructor parameters so the
    coordinator is instantiable without a QApplication.
    """

    def __init__(
        self,
        *,
        refresh_template_list_fn: Callable[[], None],
        load_template_fn: Callable[[str], None],
        save_template_fn: Callable[[], None],
        logger: LoggerPort | None = None,
    ) -> None:
        if refresh_template_list_fn is None:
            raise ValueError("VideoTemplateCoordinator requires a non-None refresh_template_list_fn")
        if load_template_fn is None:
            raise ValueError("VideoTemplateCoordinator requires a non-None load_template_fn")
        if save_template_fn is None:
            raise ValueError("VideoTemplateCoordinator requires a non-None save_template_fn")
        self._refresh_template_list_fn = refresh_template_list_fn
        self._load_template_fn = load_template_fn
        self._save_template_fn = save_template_fn
        self._logger = logger

    def refresh_template_list(self) -> None:
        """Refresh available templates in the current context."""
        return self._refresh_template_list_fn()

    def load_selected_template(self, tpl_id: str) -> None:
        """Load the currently selected template into the active workspace."""
        return self._load_template_fn(tpl_id)

    def save_template(self) -> None:
        """Persist the active template through the configured storage path."""
        return self._save_template_fn()
