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
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import Model, predict

PORT = int(os.environ.get("MIDI_PORT", "4010"))

# Load the model once at import time (this is the whole point of a service).
MODEL = Model(ICASSP_2022_MODEL_PATH)
# Basic Pitch's interpreter is not thread-safe; serialise predictions.
LOCK = threading.Lock()


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
    def _reply(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply({"ok": True})
        else:
            self._reply({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/transcribe":
            self._reply({"ok": False, "error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
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
                with urllib.request.urlopen(url, timeout=120) as resp:
                    audio = resp.read()
            else:
                audio = body
            if not audio:
                self._reply({"ok": False, "error": "empty audio"}, 400)
                return
            self._reply(transcribe(audio, name))
        except Exception as exc:  # noqa: BLE001
            self._reply({"ok": False, "error": str(exc)})

    def log_message(self, *args) -> None:  # silence per-request logs
        pass


if __name__ == "__main__":
    print(f"[midi-service] listening on 127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
