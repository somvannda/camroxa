"""Background DistroKid Connect (Google Sign-In) worker — keep UI responsive."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from features.distrokid.services.browser import BrowserAutomation
from features.distrokid.services.distrokid import DistroKidAutomation


class DistroKidConnectWorker(QThread):
    progressed = Signal(str)
    succeeded = Signal(bool)
    failed = Signal(str)

    def __init__(self, *, keep_browser_open: bool = True, parent=None) -> None:
        super().__init__(parent)
        self._keep_open = keep_browser_open
        self._browser: BrowserAutomation | None = None

    def run(self) -> None:
        try:
            self.progressed.emit("Launching DistroKid browser…")
            browser = BrowserAutomation(headless=False)
            self._browser = browser
            browser.launch()
            dk = DistroKidAutomation(browser)
            dk.set_callbacks(on_log=lambda msg: self.progressed.emit(str(msg)))
            ok = bool(dk.login())
            if ok:
                self.progressed.emit("DistroKid session connected.")
            else:
                self.progressed.emit("DistroKid login did not complete.")
            if not self._keep_open:
                browser.close()
                self._browser = None
            self.succeeded.emit(ok)
        except Exception as exc:  # noqa: BLE001
            try:
                if self._browser is not None:
                    self._browser.close()
            except Exception:
                pass
            self._browser = None
            self.failed.emit(str(exc) or "DistroKid connect failed.")
