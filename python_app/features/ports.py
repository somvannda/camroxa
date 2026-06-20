"""Shared protocol definitions for feature coordinator dependency injection.

These protocols define the interfaces that coordinators depend on, enabling
testability without Qt and enforcing loose coupling between layers.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol


class EventBusPort(Protocol):
    """Minimal event bus interface for coordinator use."""

    def emit(self, event_name: str, payload: dict) -> None: ...


class LoggerPort(Protocol):
    """Logging interface to decouple from app.logging."""

    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...


class DbCfgAccessor(Protocol):
    """Callable that returns the current database configuration."""

    def __call__(self) -> Any: ...


class SettingsAccessor(Protocol):
    """Callable that returns current application settings dict."""

    def __call__(self) -> dict: ...


class TimerHandle(Protocol):
    """Abstract handle for a periodic timer."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def is_active(self) -> bool: ...


# Type aliases for UI interaction callables
ConfirmFn = Callable[[str, str], None]
InputFn = Callable[[str, str, list[str], int], tuple[str, bool]]
TimerFactory = Callable[[int, Callable[[], None]], TimerHandle]


# -- UI interaction callables for coordinator decoupling --

# Confirmation dialog that returns True if user clicks Yes
ConfirmQuestionFn = Callable[[str, str], bool]

# Warning dialog (informational, no return value needed)
WarningFn = Callable[[str, str], None]

# File open dialog: (title, filter) -> path or ""
FileDialogFn = Callable[[str, str], str]

# Directory selection dialog: (title, default_dir) -> path or ""
DirDialogFn = Callable[[str, str], str]

# Populates a table widget with rows of string cells.
# Each row is a list of (column_index, text, data_role_value) tuples.
TablePopulateFn = Callable[[list[list[tuple[int, str, str]]]], None]

# Returns items from a list widget as list of (display_text, user_role_data) tuples.
ListItemsFn = Callable[[], list[tuple[str, str]]]

# Populates a list widget with (display_text, user_role_data) items.
ListPopulateFn = Callable[[list[tuple[str, str]]], None]

# Reads selected items from a list widget as list of user_role_data strings.
ListSelectedItemsFn = Callable[[], list[str]]

# Process pending UI events (replacement for QApplication.processEvents)
ProcessEventsFn = Callable[[], None]

# Deferred call: schedule a callback after a delay (replacement for QTimer.singleShot)
# (delay_ms, callback) -> None
DeferCallFn = Callable[[int, Callable[[], None]], None]

# Informational dialog (no return value needed)
InformationFn = Callable[[str, str], None]

# Copies text to system clipboard
ClipboardFn = Callable[[str], None]

# Shows a context menu for a progress row and dispatches the chosen action.
# (pos, row_index, meta) -> None
ContextMenuFn = Callable[[Any, int, dict], None]

# Shows an indeterminate progress dialog. Returns a handle to close/update it.
# (title, message) -> ProgressDialogHandle
ShowProgressDialogFn = Callable[[str, str], "ProgressDialogHandle"]


class ProgressDialogHandle(Protocol):
    """Handle for an indeterminate progress dialog."""

    def set_label(self, text: str) -> None: ...
    def close(self) -> None: ...


class UIInteractionPort(Protocol):
    """UI interaction callables injected into coordinators."""

    confirm_fn: ConfirmFn
    input_fn: InputFn
    timer_factory: TimerFactory
