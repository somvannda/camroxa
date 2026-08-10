"""Ensure only one Camxora desktop process runs at a time per build env."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QLocalServer, QLocalSocket

# Production (and non-sandbox) lock ΓÇö keep stable so existing installs keep
# focusing the same window. Sandbox uses a distinct suffix so it can run
# alongside a production install for side-by-side testing.
_PRODUCTION_SERVER_NAME = "Camxora.DesktopStudio.SingleInstance.v1"
_ACTIVATE = b"activate\n"


def single_instance_server_name(build_env: str | None = None) -> str:
    """Local-server name for the single-instance lock.

    Production always uses ``Camxora.DesktopStudio.SingleInstance.v1``.
    Sandbox uses a separate name so one sandbox + one production app can run
    at the same time. Development shares the production name.
    """
    env = (build_env or "").strip().lower()
    if not env:
        try:
            from shared.services.build_config import build_environment

            env = build_environment()
        except Exception:
            env = "development"
    if env == "sandbox":
        return f"{_PRODUCTION_SERVER_NAME}.sandbox"
    return _PRODUCTION_SERVER_NAME


class SingleInstanceGuard(QObject):
    """Primary-instance local server; secondary instances ping it then exit."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server: QLocalServer | None = None
        self._on_activate: Callable[[], None] | None = None
        self._server_name = single_instance_server_name()

    def try_become_primary(self) -> bool:
        """Return True if this process owns the instance lock."""
        name = self._server_name
        probe = QLocalSocket(self)
        probe.connectToServer(name)
        if probe.waitForConnected(200):
            probe.write(_ACTIVATE)
            probe.flush()
            probe.waitForBytesWritten(200)
            probe.disconnectFromServer()
            if probe.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                probe.waitForDisconnected(200)
            return False

        # Stale server after a crash ΓÇö remove then listen.
        QLocalServer.removeServer(name)
        server = QLocalServer(self)
        if not server.listen(name):
            # Another process won the race between connect and listen.
            return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def set_activate_handler(self, handler: Callable[[], None]) -> None:
        self._on_activate = handler

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            # Drain any payload, then activate the existing window.
            if socket.bytesAvailable() > 0:
                try:
                    _ = bytes(socket.readAll())
                except Exception:
                    pass
            else:
                socket.readyRead.connect(lambda sock=socket: self._read_activate(sock))
            try:
                socket.disconnectFromServer()
            except Exception:
                pass
            self._emit_activate()

    def _read_activate(self, socket: QLocalSocket) -> None:
        try:
            _ = bytes(socket.readAll())
        except Exception:
            pass
        try:
            socket.disconnectFromServer()
        except Exception:
            pass
        self._emit_activate()

    def _emit_activate(self) -> None:
        handler = self._on_activate
        if handler is None:
            return
        try:
            handler()
        except Exception:
            return


def notify_already_running() -> None:
    """Best-effort message when a second instance is blocked."""
    try:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            None,
            "Camxora",
            "Camxora is already running.\n\nThe existing window will be brought to the front.",
        )
    except Exception:
        pass
