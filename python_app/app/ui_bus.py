from PyQt6.QtCore import QObject, pyqtSignal


class UiBus(QObject):
    export_event = pyqtSignal(dict)
    export_done = pyqtSignal(dict)
    music_event = pyqtSignal(dict)
    ui_invoke = pyqtSignal(object)

