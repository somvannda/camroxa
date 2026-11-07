"""Resumable-upload contract: prove we honour 308 offsets and surface errors.

The real bugs this guards against: sending the whole file again after a resumed
transfer, mis-reading the Range header, and swallowing a 4xx into a generic
failure.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from shared.lib.youtube_direct import upload_file

VIDEO_ID = "fake12345"
CHUNK = 4


class _FakeGoogle(BaseHTTPRequestHandler):
    """Minimal resumable endpoint: 308 with a Range, then 200 with the id."""

    server_version = "FakeGoogle/1.0"

    def log_message(self, *_args: object) -> None:  # keep pytest output clean
        return

    def do_PUT(self) -> None:  # noqa: N802 - http.server API
        state = self.server.state  # type: ignore[attr-defined]
        header = self.headers.get("Content-Range", "")
        if header.startswith("bytes */"):
            # Resume probe: tell the client how much already landed.
            if state["received"] > 0:
                self._send_308(state["received"])
            else:
                self._send_308(0)
            return

        if state.get("fail"):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":{"message":"invalidTags"}}')
            return

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        state["chunks"].append((header, len(body)))
        state["received"] += len(body)
        if state["received"] >= state["size"]:
            payload = f'{{"id":"{VIDEO_ID}"}}'.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self._send_308(state["received"])

    def _send_308(self, received: int) -> None:
        self.send_response(308)
        self.send_header("Range", f"bytes=0-{max(received - 1, 0)}")
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def google(request):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeGoogle)
    server.state = {  # type: ignore[attr-defined]
        "size": 10,
        "received": 0,
        "chunks": [],
        "fail": False,
    }
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _file(tmp_path: Path, size: int = 10) -> Path:
    target = tmp_path / "merged.mp4"
    target.write_bytes(b"x" * size)
    return target


def _session_url(server: ThreadingHTTPServer) -> str:
    host, port = server.server_address[:2]
    return f"http://{host}:{port}/session"


def test_upload_sends_chunks_and_returns_the_video_id(google, tmp_path) -> None:
    path = _file(tmp_path)
    progress: list[tuple[int, int]] = []

    result = upload_file(
        _session_url(google),
        path,
        chunk_bytes=CHUNK,
        on_progress=lambda sent, total: progress.append((sent, total)),
    )

    assert result["id"] == VIDEO_ID
    assert google.state["received"] == 10
    assert progress[-1] == (10, 10)
    # 10 bytes in 4-byte chunks: 3 uploads after the probe.
    assert len(google.state["chunks"]) == 3


def test_a_resumed_upload_continues_from_the_reported_offset(google, tmp_path) -> None:
    # Four bytes already landed server-side before this attempt.
    google.state["received"] = 4
    path = _file(tmp_path)

    result = upload_file(_session_url(google), path, chunk_bytes=CHUNK)

    assert result["id"] == VIDEO_ID
    ranges = [header for header, _length in google.state["chunks"]]
    assert ranges[0].startswith("bytes 4-"), "must resume at the server's offset"
    assert all(not r.startswith("bytes 0-") for r in ranges), "must not resend the first part"


def test_a_rejected_upload_surfaces_the_provider_message(google, tmp_path) -> None:
    google.state["fail"] = True
    path = _file(tmp_path)

    with pytest.raises(RuntimeError) as excinfo:
        upload_file(_session_url(google), path, chunk_bytes=CHUNK)

    assert "400" in str(excinfo.value)
    assert "invalidTags" in str(excinfo.value)
