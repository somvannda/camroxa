from pathlib import Path

import pytest

from studio.core.project_state import ProjectState
from studio.ui.library_panel import MediaTab


def test_import_runs_off_the_ui_thread_and_shows_busy_state(qtbot, sample_audio: Path):
    """Regression test: dropping files used to call import_files() directly
    on the UI thread, freezing the app with no feedback for the whole
    probe+thumbnail duration."""
    state = ProjectState()
    tab = MediaTab(state)
    qtbot.addWidget(tab)

    toasts: list[str] = []
    tab.toast_requested.connect(toasts.append)
    imported: list[list] = []
    tab.media_imported.connect(imported.append)

    tab._on_files_dropped([str(sample_audio)])

    # The import must be running in the background, not already finished
    # synchronously, and the drop zone must reflect the busy state.
    assert tab.import_zone._busy is True
    assert any("Importing" in t for t in toasts)

    qtbot.waitUntil(lambda: len(imported) == 1, timeout=10000)

    assert tab.import_zone._busy is False
    assert len(imported[0]) == 1
    assert imported[0][0].type == "audio"
    assert any("Imported" in t for t in toasts)
    assert len(state.project.media_library) == 1

    tab.wait_for_import_to_finish()


def test_dropping_files_while_importing_is_rejected_with_a_toast(qtbot, sample_audio: Path):
    state = ProjectState()
    tab = MediaTab(state)
    qtbot.addWidget(tab)
    toasts: list[str] = []
    tab.toast_requested.connect(toasts.append)
    imported: list[list] = []
    tab.media_imported.connect(imported.append)

    tab._on_files_dropped([str(sample_audio)])
    tab._on_files_dropped([str(sample_audio)])  # dropped again while still importing

    qtbot.waitUntil(lambda: len(imported) == 1, timeout=10000)

    assert any("please wait" in t for t in toasts)
    assert len(imported) == 1  # the second drop was rejected, not queued
    assert len(state.project.media_library) == 1

    tab.wait_for_import_to_finish()


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_import_zone_ignores_drops_and_clicks_while_busy(qtbot, sample_audio: Path):
    state = ProjectState()
    tab = MediaTab(state)
    qtbot.addWidget(tab)
    imported: list[list] = []
    tab.media_imported.connect(imported.append)

    tab._on_files_dropped([str(sample_audio)])
    assert tab.import_zone._busy is True

    clicked_dialog = []
    tab.import_zone._open_file_dialog = lambda: clicked_dialog.append(True)
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QMouseEvent

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPoint(5, 5),
        _Qt.MouseButton.LeftButton,
        _Qt.MouseButton.LeftButton,
        _Qt.KeyboardModifier.NoModifier,
    )
    tab.import_zone.mousePressEvent(event)
    assert clicked_dialog == []  # click-to-browse is disabled while busy

    qtbot.waitUntil(lambda: len(imported) == 1, timeout=10000)
    tab.wait_for_import_to_finish()
