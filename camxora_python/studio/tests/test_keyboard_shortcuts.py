from PySide6.QtWidgets import QLineEdit, QPushButton

from studio.ui.main_window import MainWindow


def test_space_playback_blocked_while_typing(qtbot):
    line = QLineEdit()
    qtbot.addWidget(line)
    assert MainWindow._focus_blocks_space_playback(line) is True


def test_space_playback_allowed_on_buttons(qtbot):
    btn = QPushButton()
    qtbot.addWidget(btn)
    assert MainWindow._focus_blocks_space_playback(btn) is False
