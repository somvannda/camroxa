"""
FooterController — owns footer status-bar state and refresh logic.

Extracted from MainWindow as part of the God-class refactor.
Requirements: 3.1, 3.2, 3.3, 3.5, 3.6
"""
from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QLabel


class FooterController:
    """Owns the three footer status string fields and the priority/composition
    rule that previously lived in ``MainWindow._refresh_footer_status``.

    The ``label_accessor`` callable is called lazily on each ``refresh()`` so
    that the controller can be constructed before the Qt label widget exists.
    Tests inject a callable that returns a ``MagicMock`` (or ``None``) to
    exercise the controller without a real ``QLabel``.
    """

    def __init__(
        self,
        label_accessor: Callable[[], QLabel | None],
    ) -> None:
        self._label_accessor = label_accessor
        self._global_status_message: str = ""
        self._music_status_message: str = ""
        self._music_suno_status_message: str = ""

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_status(self, message: str, *, source: str = "") -> None:
        """Set the global status message and refresh the footer label.

        The ``source`` keyword argument is accepted for API compatibility but
        has no effect on the stored message.
        """
        self._global_status_message = message
        self.refresh()

    def set_music_status(self, message: str) -> None:
        """Set the music-domain status message and refresh the footer label."""
        self._music_status_message = message
        self.refresh()

    def set_suno_status(self, message: str) -> None:
        """Set the Suno (music-generation sub-task) status message and refresh."""
        self._music_suno_status_message = message
        self.refresh()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Apply the composition rule and push the result to the footer label.

        Composition rule
        ----------------
        1. If ``_music_suno_status_message`` is non-empty **and**
           ``_global_status_message == _music_status_message``:
               display = f"{_music_status_message} · {_music_suno_status_message}"
        2. Otherwise:
               display = _global_status_message
                         or _music_status_message (if global is empty)
                         or "Ready"              (if all three are empty)

        Guards
        ------
        - If ``label_accessor()`` returns ``None`` the update is silently
          skipped (label not yet created or already destroyed).
        - If ``setText`` raises ``RuntimeError`` (destroyed C++ object) the
          exception is silently swallowed.
        """
        # Determine display text according to the composition rule.
        if (
            self._music_suno_status_message
            and self._global_status_message == self._music_status_message
        ):
            display = (
                f"{self._music_status_message} · {self._music_suno_status_message}"
            )
        else:
            display = (
                self._global_status_message
                or self._music_status_message
                or "Ready"
            )

        # Obtain the label; silently skip if unavailable.
        label = self._label_accessor()
        if label is None:
            return

        # Push the text; silently skip if the underlying C++ object is gone.
        try:
            label.setText(display)
        except RuntimeError:
            pass
