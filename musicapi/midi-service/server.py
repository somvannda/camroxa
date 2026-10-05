#!/usr/bin/env python3
"""CamXora musicapi MIDI microservice — Basic Pitch audio-to-MIDI.

Suno exposes no MIDI API (it is a Studio-only feature), so — like sunoapi.org,
which returns its own `midiData` — we transcribe the separated stems ourselves
with Spotify's Basic Pitch (running on `tflite-runtime`, no TensorFlow). This
runs as a localhost HTTP service so the model loads once; the Node API calls it
per stem.

Endpoints
  GET  /health      -> {"ok": true}
  POST /transcribe  -> {"ok": true, "name": "...", "notes": [{pitch,start,end,velocity}]}

`/transcribe` accepts either:
  - raw audio bytes (any librosa/ffmpeg-readable container), with the instrument
    name in the `x-stem-name` header, or
  - JSON {"url": "<audio url>", "name": "Vocals"} (downloaded server-side).

Hardening: a bounded worker pool, a request-body cap, a socket timeout, an
SSRF guard on the `url` field, and an optional shared-secret header
(MIDI_SERVICE_TOKEN) — the Node caller sends it when configured.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import tempfile
import threading
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import Model, predict

PORT = int(os.environ.get("MIDI_PORT", "4010"))
MAX_BODY_BYTES = int(os.environ.get("MIDI_MAX_BODY_BYTES", str(64 * 1024 * 1024)))
MAX_DOWNLOAD_BYTES = int(os.environ.get("MIDI_MAX_DOWNLOAD_BYTES", str(64 * 1024 * 1024)))
MAX_CONCURRENT = max(1, int(os.environ.get("MIDI_MAX_CONCURRENT", "2")))
REQUIRED_TOKEN = (os.environ.get("MIDI_SERVICE_TOKEN") or "").strip()

# Load the model once at import time (this is the whole point of a service).
MODEL = Model(ICASSP_2022_MODEL_PATH)
# Basic Pitch's interpreter is not thread-safe; serialise predictions.
LOCK = threading.Lock()
# Bound in-flight requests so a flood cannot spawn unbounded worker threads.
SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT)


def _is_public_host(host: str) -> bool:
    """True only when every address `host` resolves to is globally routable."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("url must use http or https")
    if not parsed.hostname or not _is_public_host(parsed.hostname):
        raise ValueError("url host is not allowed")


def _download_audio(url: str, timeout: int = 120) -> bytes:
    _assert_public_http_url(url)
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("downloaded audio is too large")
    return data


def transcribe(audio: bytes, name: str) -> dict:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(audio)
        with LOCK:
            _model_output, _midi, note_events = predict(path, MODEL)
        notes = [
            {
                "pitch": int(n[2]),
                "start": float(n[0]),
                "end": float(n[1]),
                "velocity": float(n[3]),
            }
            for n in note_events
        ]
        return {"ok": True, "name": name, "notes": notes}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    # Applies an idle-socket timeout so a slow/trickling client cannot pin a
    # worker thread forever.
    timeout = 300

    def _reply(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        if not REQUIRED_TOKEN:
            return True
        return self.headers.get("x-service-token", "") == REQUIRED_TOKEN

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply({"ok": True})
        else:
            self._reply({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/transcribe":
            self._reply({"ok": False, "error": "not found"}, 404)
            return
        if not self._authorized():
            self._reply({"ok": False, "error": "unauthorized"}, 401)
            return
        try:
            raw_length = self.headers.get("content-length", "0")
            try:
                length = int(raw_length or "0")
            except ValueError:
                self._reply({"ok": False, "error": "invalid content-length"}, 400)
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._reply({"ok": False, "error": "request body too large"}, 413)
                return
            body = self.rfile.read(length) if length else b""
            name = self.headers.get("x-stem-name", "Instrument")
            ctype = (self.headers.get("content-type") or "").lower()
            if ctype.startswith("application/json"):
                data = json.loads(body or b"{}")
                url = data.get("url")
                name = data.get("name") or name
                if not url:
                    self._reply({"ok": False, "error": "url required"}, 400)
                    return
                audio = _download_audio(url)
            else:
                audio = body
            if not audio:
                self._reply({"ok": False, "error": "empty audio"}, 400)
                return
            with SLOTS:
                result = transcribe(audio, name)
            self._reply(result)
        except ValueError as exc:
            self._reply({"ok": False, "error": str(exc)}, 400)
        except Exception:  # noqa: BLE001
            # Log internals server-side; never reflect them to the caller.
            print(f"[midi-service] transcribe failed:\n{traceback.format_exc()}", flush=True)
            self._reply({"ok": False, "error": "transcription failed"}, 500)

    def log_message(self, *args) -> None:  # silence per-request logs
        pass


if __name__ == "__main__":
    print(f"[midi-service] listening on 127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
