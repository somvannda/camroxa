"""Qt-side adapters for UI interaction protocols.

This module provides concrete PyQt6 implementations of the UI interaction
callables defined in features/ports.py. These adapters bridge the gap between
the abstract protocols used by coordinators and the actual Qt widget APIs,
allowing coordinators to remain decoupled from PyQt6.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


class QtTimerHandle:
    """Concrete timer handle wrapping a QTimer instance.

    Implements the TimerHandle protocol from features/ports.py.
    """

    def __init__(self, interval_ms: int, callback: Callable[[], None], parent: QWidget) -> None:
        self._timer = QTimer(parent)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(callback)

    def start(self) -> None:
        """Start the timer."""
        self._timer.start()

    def stop(self) -> None:
        """Stop the timer."""
        self._timer.stop()

    def is_active(self) -> bool:
        """Return whether the timer is currently running."""
        return self._timer.isActive()


def make_confirm_fn(parent: QWidget) -> Callable[[str, str], None]:
    """Create a confirmation callable that wraps QMessageBox.warning.

    Args:
        parent: The parent widget for the message box.

    Returns:
        A callable with signature (title: str, message: str) -> None.
    """

    def confirm(title: str, message: str) -> None:
        QMessageBox.warning(parent, title, message)

    return confirm


def make_input_fn(parent: QWidget) -> Callable[[str, str, list[str], int], tuple[str, bool]]:
    """Create an input callable that wraps QInputDialog.getItem.

    Args:
        parent: The parent widget for the input dialog.

    Returns:
        A callable with signature
        (title: str, label: str, items: list[str], current: int) -> tuple[str, bool].
    """

    def input_fn(title: str, label: str, items: list[str], current: int) -> tuple[str, bool]:
        return QInputDialog.getItem(parent, title, label, items, current, False)

    return input_fn


def make_timer_factory(parent: QWidget) -> Callable[[int, Callable[[], None]], QtTimerHandle]:
    """Create a timer factory callable that produces QtTimerHandle instances.

    Args:
        parent: The parent widget for created timers.

    Returns:
        A callable with signature
        (interval_ms: int, callback: Callable[[], None]) -> QtTimerHandle.
    """

    def timer_factory(interval_ms: int, callback: Callable[[], None]) -> QtTimerHandle:
        return QtTimerHandle(interval_ms, callback, parent)

    return timer_factory


def make_confirm_question_fn(parent: QWidget) -> Callable[[str, str], bool]:
    """Create a confirmation question callable that wraps QMessageBox.question.

    Args:
        parent: The parent widget for the message box.

    Returns:
        A callable with signature (title: str, message: str) -> bool.
        Returns True if the user clicks Yes, False otherwise.
    """

    def confirm_question(title: str, message: str) -> bool:
        result = QMessageBox.question(parent, title, message)
        return result == QMessageBox.StandardButton.Yes

    return confirm_question


def make_warning_fn(parent: QWidget) -> Callable[[str, str], None]:
    """Create a warning dialog callable that wraps QMessageBox.warning.

    Args:
        parent: The parent widget for the message box.

    Returns:
        A callable with signature (title: str, message: str) -> None.
    """

    def warning(title: str, message: str) -> None:
        QMessageBox.warning(parent, title, message)

    return warning


def make_file_dialog_fn(parent: QWidget) -> Callable[[str, str], str]:
    """Create a file dialog callable that wraps QFileDialog.getOpenFileName.

    Args:
        parent: The parent widget for the file dialog.

    Returns:
        A callable with signature (title: str, filter: str) -> str.
        Returns the selected file path, or "" if cancelled.
    """

    def file_dialog(title: str, filter: str) -> str:
        path, _ = QFileDialog.getOpenFileName(parent, title, "", filter)
        return path or ""

    return file_dialog


def make_dir_dialog_fn(parent: QWidget) -> Callable[[str, str], str]:
    """Create a directory dialog callable that wraps QFileDialog.getExistingDirectory.

    Args:
        parent: The parent widget for the directory dialog.

    Returns:
        A callable with signature (title: str, default_dir: str) -> str.
        Returns the selected directory path, or "" if cancelled.
    """

    def dir_dialog(title: str, default_dir: str) -> str:
        path = QFileDialog.getExistingDirectory(parent, title, default_dir)
        return path or ""

    return dir_dialog


def make_table_populate_fn(table_widget: QTableWidget) -> Callable[[list[list[tuple[int, str, str]]]], None]:
    """Create a table populate callable that fills a QTableWidget with rows.

    Args:
        table_widget: The QTableWidget to populate.

    Returns:
        A callable with signature (rows: list[list[tuple[int, str, str]]]) -> None.
        Each row is a list of (column_index, text, user_role_data) tuples.
    """

    def table_populate(rows: list[list[tuple[int, str, str]]]) -> None:
        table_widget.clearContents()
        table_widget.setRowCount(len(rows))
        for row_idx, cells in enumerate(rows):
            for col_idx, text, data in cells:
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, data)
                table_widget.setItem(row_idx, col_idx, item)

    return table_populate


def make_list_items_fn(list_widget: QListWidget) -> Callable[[], list[tuple[str, str]]]:
    """Create a list items callable that reads items from a QListWidget.

    Args:
        list_widget: The QListWidget to read items from.

    Returns:
        A callable with signature () -> list[tuple[str, str]].
        Returns a list of (display_text, user_role_data) tuples.
    """

    def list_items() -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item is not None:
                text = item.text()
                data = item.data(Qt.ItemDataRole.UserRole) or ""
                items.append((text, str(data)))
        return items

    return list_items


def make_list_populate_fn(list_widget: QListWidget) -> Callable[[list[tuple[str, str]]], None]:
    """Create a list populate callable that fills a QListWidget with items.

    Args:
        list_widget: The QListWidget to populate.

    Returns:
        A callable with signature (items: list[tuple[str, str]]) -> None.
        Each item is a (display_text, user_role_data) tuple.
    """

    def list_populate(items: list[tuple[str, str]]) -> None:
        list_widget.clear()
        for text, data in items:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, data)
            list_widget.addItem(item)

    return list_populate


def make_process_events_fn() -> Callable[[], None]:
    """Create a process events callable that wraps QApplication.processEvents.

    Returns:
        A callable with signature () -> None that processes pending UI events.
    """

    def process_events() -> None:
        QApplication.processEvents()

    return process_events


def make_defer_call_fn() -> Callable[[int, Callable[[], None]], None]:
    """Create a deferred call callable that wraps QTimer.singleShot.

    Returns:
        A callable with signature (delay_ms: int, callback: Callable[[], None]) -> None.
        Schedules ``callback`` to run after ``delay_ms`` milliseconds on the main thread.
    """

    def defer_call(delay_ms: int, callback: Callable[[], None]) -> None:
        QTimer.singleShot(delay_ms, callback)

    return defer_call
