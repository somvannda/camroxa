"""Google sign-in for the desktop studio.

Google still redirects to the same registered https callback that music.camxora.com
uses, so no native-app redirect has to be added to the Google Cloud Console. The
flow is:

1. the desktop binds a one-shot loopback listener (``127.0.0.1:<port>``),
2. ``GET /auth/google/url?desktop_port=<port>`` signs that port into the state,
3. the browser performs consent, then ``/auth/callback`` on the website forwards
   the browser to ``http://127.0.0.1:<port>/google/callback``,
4. the desktop posts the code to ``POST /auth/google/callback``, which verifies
   the signed state and exchanges the code with the client secret.

Only the app ever sees tokens; the browser carries an authorization code that is
useless without the server-side secret.

The port is fixed (``DEFAULT_LOOPBACK_PORT``) so a second window fails loudly with
a clear message instead of racing for the hand-off. Operations can change it with
``CAMXORA_OAUTH_LOOPBACK_PORT``.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_LOOPBACK_PORT = 41580
CALLBACK_PATH = "/google/callback"
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_WAIT_TIMEOUT_SECONDS = 300.0

_SUCCESS_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CAMXORA — signed in</title>
<style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#0a0e27;
color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif}
.card{max-width:420px;padding:32px 36px;border-radius:16px;background:#0c1230;
border:1px solid rgba(124,58,237,.35);text-align:center}
h1{margin:0 0 8px;font-size:20px}p{margin:0;color:#94a3b8;font-size:14px;line-height:1.6}
</style></head><body><div class="card">
<h1>You're signed in</h1>
<p>Return to the CAMXORA studio. You can close this tab.</p>
</div></body></html>
"""

_FAILURE_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CAMXORA — sign-in cancelled</title>
<style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#0a0e27;
color:#f8fafc;font-family:'Segoe UI',system-ui,sans-serif}
.card{max-width:420px;padding:32px 36px;border-radius:16px;background:#0c1230;
border:1px solid rgba(248,113,113,.35);text-align:center}
h1{margin:0 0 8px;font-size:20px}p{margin:0;color:#94a3b8;font-size:14px;line-height:1.6}
</style></head><body><div class="card">
<h1>Sign-in was not completed</h1>
<p>Return to the CAMXORA studio and try again.</p>
</div></body></html>
"""


class GoogleSignInError(Exception):
    """Raised when the desktop Google sign-in flow cannot complete."""


class _LoopbackHTTPServer(ThreadingHTTPServer):
    """Loopback listener that refuses to share its port.

    Windows lets two sockets bind the same address when SO_REUSEADDR is set
    (the http.server default), which would silently hand the redirect to
    whichever window bound last. Only the exclusive bind is correct here.
    """

    allow_reuse_address = os.name != "nt"
    allow_reuse_port = False


@dataclass(frozen=True, slots=True)
class GoogleLoopbackResult:
    code: str
    state: str


def loopback_port_from_env() -> int:
    raw = (os.environ.get("CAMXORA_OAUTH_LOOPBACK_PORT") or "").strip()
    if not raw:
        return DEFAULT_LOOPBACK_PORT
    try:
        port = int(raw)
    except ValueError:
        return DEFAULT_LOOPBACK_PORT
    return port if 1 <= port <= 65535 else DEFAULT_LOOPBACK_PORT


class GoogleLoopbackServer:
    """One-shot loopback listener that receives the Google redirect."""

    def __init__(self, port: int | None = None) -> None:
        self._port = int(port if port is not None else loopback_port_from_env())
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._done = threading.Event()
        self._result: GoogleLoopbackResult | None = None
        self._error: str | None = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return int(self._server.server_address[1])
        return self._port

    @property
    def redirect_uri(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.port}{CALLBACK_PATH}"

    def start(self) -> str:
        if self._server is not None:
            return self.redirect_uri
        handler = _build_handler(self)
        try:
            self._server = _LoopbackHTTPServer((LOOPBACK_HOST, self._port), handler)
        except OSError as exc:
            raise GoogleSignInError(
                f"Port {self._port} is busy. Close the other CAMXORA window and try again."
            ) from exc
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._serve,
            name="GoogleOAuthLoopback",
            daemon=True,
        )
        self._thread.start()
        return self.redirect_uri

    def wait(self, timeout: float = DEFAULT_WAIT_TIMEOUT_SECONDS) -> GoogleLoopbackResult:
        if not self._done.wait(timeout):
            raise GoogleSignInError("Google sign-in timed out. Please try again.")
        if self._result is None:
            raise GoogleSignInError(self._error or "Google sign-in was cancelled.")
        return self._result

    def close(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2)

    def _serve(self) -> None:
        server = self._server
        if server is not None:
            try:
                server.serve_forever(poll_interval=0.2)
            except Exception:
                pass

    def _complete(self, *, code: str, state: str, error: str) -> None:
        # The browser may retry the request; only the first outcome counts.
        if self._done.is_set():
            return
        if error:
            self._error = "Google sign-in was cancelled."
        elif code and state:
            self._result = GoogleLoopbackResult(code=code, state=state)
        else:
            self._error = "Google did not return an authorization code."
        self._done.set()


def _build_handler(owner: GoogleLoopbackServer) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlparse(self.path)
            if parsed.path != CALLBACK_PATH:
                self._respond(404, "<h1>Not found</h1>")
                return
            params = parse_qs(parsed.query)
            code = (params.get("code") or [""])[0]
            state = (params.get("state") or [""])[0]
            error = (params.get("error") or [""])[0]
            owner._complete(code=code, state=state, error=error)
            self._respond(200, _FAILURE_HTML if error or not code else _SUCCESS_HTML)

        def _respond(self, status: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except Exception:
                pass

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - silence access log
            return

    return _Handler
