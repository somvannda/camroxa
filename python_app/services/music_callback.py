from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from typing import Any, Callable


class CallbackServerManager:
    def __init__(self, callback_path: str = "/suno/callback", on_callback: Callable[[Any], None] | None = None) -> None:
        self.callback_path = callback_path if str(callback_path or "").startswith("/") else f"/{callback_path}"
        self.on_callback = on_callback
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None

    def status(self) -> dict:
        port = self.port
        return {
            "running": self._server is not None,
            "port": port,
            "callbackPath": self.callback_path,
            "callbackUrl": f"http://127.0.0.1:{port}{self.callback_path}" if port else None,
            "lastError": self._last_error,
        }

    @property
    def port(self) -> int | None:
        if self._server is None:
            return None
        server_port = getattr(self._server, "server_port", None)
        return int(server_port) if server_port else None

    def start(self) -> dict:
        if self._server is not None:
            return self.status()

        manager = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                try:
                    if self.path != manager.callback_path:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b"not found")
                        return
                    length = int(self.headers.get("content-length", "0") or 0)
                    if length > 2_000_000:
                        raise ValueError("payload too large")
                    raw = self.rfile.read(length) if length > 0 else b""
                    payload = json.loads(raw.decode("utf-8")) if raw.strip() else None
                    if callable(manager.on_callback):
                        manager.on_callback(payload)
                    self.send_response(200)
                    self.send_header("content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                except Exception as exc:
                    manager._last_error = str(exc)
                    self.send_response(400)
                    self.send_header("content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "message": str(exc)}).encode("utf-8"))

            def log_message(self, format: str, *args: Any) -> None:
                return

        try:
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self._server = server
            self._thread = thread
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
        return self.status()

    def stop(self) -> dict:
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        self._thread = None
        return self.status()
