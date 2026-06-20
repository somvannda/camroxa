from __future__ import annotations

from PyQt6.QtCore import QDate, QEvent, QTimer
from PyQt6.QtWidgets import QDateEdit, QMainWindow, QVBoxLayout, QWidget

from ..views.components import AspectRatioBox, SpectrumPreview


class AppDateEdit(QDateEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        if self.calendarWidget():
            self.calendarWidget().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj == self.calendarWidget() and ev.type() == QEvent.Type.Show:
            if self.date() == self.minimumDate():
                today = QDate.currentDate()

                def _move_cal():
                    self.calendarWidget().setCurrentPage(today.year(), today.month())
                    self.calendarWidget().setSelectedDate(today)

                QTimer.singleShot(0, _move_cal)
        return super().eventFilter(obj, ev)


class PopoutPreviewWindow(QMainWindow):
    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self._main = main
        self.setWindowTitle("Pop Out Live Preview")
        self.resize(960, 540)
        self.setStyleSheet("QMainWindow { background-color: #000000; }")

        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self.preview = SpectrumPreview()
        self.preview.set_template(self._main.template)
        self.preview.bg_path = self._main.preview.bg_path
        self.preview.logo_path = self._main.preview.logo_path
        self.preview.analyzer = self._main.preview.analyzer
        self.preview.current_time = self._main.preview.current_time

        lay.addWidget(AspectRatioBox(self.preview, 16, 9), 1)

        self._timer = QTimer()
        self._timer.timeout.connect(self._sync)
        self._timer.start(100)

    def _sync(self):
        try:
            self.preview.set_template(self._main.template)
            self.preview.analyzer = self._main.preview.analyzer
            self.preview.current_time = self._main.preview.current_time
            if self._main.preview.bg_path and self._main.preview.bg_path != self.preview.bg_path:
                self.preview.load_background(self._main.preview.bg_path)
            if self._main.preview.logo_path and self._main.preview.logo_path != self.preview.logo_path:
                self.preview.load_logo(self._main.preview.logo_path)
        except Exception:
            return

    def closeEvent(self, ev):
        try:
            self._timer.stop()
        except Exception:
            pass
        super().closeEvent(ev)

