#!/usr/bin/env python3
"""CamXora musicapi LRC microservice — forced lyric alignment.

The active product talks **directly to Suno** (`studio-api-prod.suno.com`), which
returns lyric *text* but no word/line timing. The legacy ``platform_api`` got
timings from the sunoapi.org reseller; this service removes that dependency by
computing alignment ourselves: transcribe the generated track with
faster-whisper (word timestamps) and snap the recognised words onto the known
lyric lines, then emit LRC.

Running it as a localhost service loads the model once; the Node API calls it
per clip. The pure functions (`tokenize`, `snap_to_lyrics`, `build_lrc`) have no
model dependency and are covered by `test_align.py`.

Endpoints
  GET  /health  -> {"ok": true, "model": "small"}
  POST /align   -> {"ok": true, "lines": [...], "words": [...], "lrc": "..."}

`/align` accepts either:
  - JSON {"url": "<audio url>", "lyrics": "<text>"} (audio downloaded server-side)
  - JSON {"audio_b64": "<base64>", "lyrics": "<text>"}
  - raw audio bytes, with the lyrics base64 in the `x-lyrics-b64` header.
"""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import threading
import urllib.request
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

PORT = int(os.environ.get("LRC_PORT", "4011"))
MODEL_NAME = os.environ.get("LRC_MODEL", "small")
DEVICE = os.environ.get("LRC_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("LRC_COMPUTE_TYPE", "int8")
LANGUAGE = os.environ.get("LRC_LANGUAGE") or None
VAD = os.environ.get("LRC_VAD", "1") != "0"

# Loaded lazily so `test_align.py` can import the pure helpers without the model.
MODEL: Any = None
# One transcription at a time, and — separately — one model *construction* at a
# time. A burst of `/align` calls arriving during a cold start used to each build
# their own copy of the model, spiking RSS past the unit's MemoryMax and getting
# the service OOM-killed on every restart (a crash loop). The load lock makes the
# first caller build it while the rest wait for the shared instance.
MODEL_LOCK = threading.Lock()
MODEL_LOAD_LOCK = threading.Lock()

# `ThreadingHTTPServer` spawns a thread per request and each one buffers the
# whole track, so an unbounded flood (a client polling for lyrics) could grow
# RSS without limit. Cap the in-flight `/align` work; over-cap requests are
# rejected with 503 so the caller falls back instead of piling up.
MAX_INFLIGHT = int(os.environ.get("LRC_MAX_INFLIGHT", "8"))
INFLIGHT = threading.BoundedSemaphore(MAX_INFLIGHT)
QUEUE_WAIT_S = float(os.environ.get("LRC_QUEUE_WAIT_S", "30"))

_TOKEN_RE = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)
_SECTION_RE = re.compile(r"^\[.*\]$")


# --------------------------------------------------------------------------- #
# Pure helpers (no model, unit-tested)                                        #
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> list[str]:
    """Word-ish tokens, punctuation dropped, for match-normalisation only."""
    return _TOKEN_RE.findall(text or "")


def normalize_token(token: str) -> str:
    return token.lower()


def split_lyric_lines(lyrics: str) -> list[str]:
    return [line.strip() for line in (lyrics or "").splitlines() if line.strip()]


def interpolate_nones(values: list[float | None]) -> list[float | None]:
    """Fill `None` entries by linear interpolation between known neighbours.

    Leading/trailing unknowns copy the nearest known value. Empty input (or all
    unknown) is returned unchanged.
    """
    length = len(values)
    known = [i for i, value in enumerate(values) if value is not None]
    if not known:
        return values
    first, last = known[0], known[-1]
    for i in range(first):
        values[i] = values[first]
    for i in range(last + 1, length):
        values[i] = values[last]
    for a, b in zip(known, known[1:]):
        if b - a <= 1:
            continue
        v0, v1 = values[a], values[b]
        assert v0 is not None and v1 is not None
        for k in range(a + 1, b):
            values[k] = v0 + (v1 - v0) * (k - a) / (b - a)
    return values


def snap_to_lyrics(
    recognized: list[dict[str, Any]], lyrics: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Snap ASR word timings onto the known lyric lines.

    Returns ``(lines, words)``. ``lines`` carries the original lyric text with a
    start time per line (what LRC needs); ``words`` carries per-lyric-token
    timings for word-level consumers. Both may be empty when nothing matched.
    """
    lines = split_lyric_lines(lyrics)
    if not lines:
        return [], []

    # Flat (line_index, original_token, normalised) tokens, in reading order.
    tokens: list[tuple[int, str, str]] = []
    for line_index, line in enumerate(lines):
        for token in tokenize(line):
            tokens.append((line_index, token, normalize_token(token)))
    if not tokens:
        return [], []

    lyric_norms = [norm for _, _, norm in tokens]
    recognized_norms = [normalize_token(str(w.get("word") or "")) for w in recognized]

    starts: list[float | None] = [None] * len(tokens)
    ends: list[float | None] = [None] * len(tokens)
    matcher = SequenceMatcher(a=recognized_norms, b=lyric_norms, autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            rec = recognized[block.a + k]
            idx = block.b + k
            starts[idx] = float(rec.get("start") or 0.0)
            ends[idx] = float(rec.get("end") or rec.get("start") or 0.0)

    if all(value is None for value in starts):
        return [], []

    # Per-line start/end from the first/last matched token, then fill gaps.
    line_start: list[float | None] = [None] * len(lines)
    line_end: list[float | None] = [None] * len(lines)
    for idx, (line_index, _, _) in enumerate(tokens):
        if starts[idx] is None:
            continue
        if line_start[line_index] is None:
            line_start[line_index] = starts[idx]
        line_end[line_index] = ends[idx]
    line_start = interpolate_nones(line_start)
    line_end = interpolate_nones(line_end)

    # Per-token starts are interpolated within their line so word-level output
    # stays monotonic even when the ASR missed a word.
    for line_index in range(len(lines)):
        positions = [i for i, (li, _, _) in enumerate(tokens) if li == line_index]
        if not positions:
            continue
        row = [starts[i] for i in positions]
        row = interpolate_nones(row)
        for slot, i in enumerate(positions):
            starts[i] = row[slot]

    out_lines: list[dict[str, Any]] = []
    out_words: list[dict[str, Any]] = []
    for idx, (line_index, original, _) in enumerate(tokens):
        start = float(starts[idx] or 0.0)
        end = float(ends[idx] if ends[idx] is not None else start)
        if end < start:
            end = start
        out_words.append({"word": original, "startS": round(start, 3), "endS": round(end, 3)})

    for line_index, text in enumerate(lines):
        start = line_start[line_index]
        if start is None:
            continue
        end = line_end[line_index] if line_end[line_index] is not None else start
        out_lines.append({"text": text, "startS": round(float(start), 3), "endS": round(float(end), 3)})

    return out_lines, out_words


def format_lrc_time(seconds: float) -> str:
    total = max(0.0, float(seconds or 0.0))
    minutes = int(total // 60)
    secs = total - minutes * 60
    return f"[{minutes:02d}:{secs:05.2f}]"


def build_lrc(lines: list[dict[str, Any]]) -> str:
    """Line-level LRC from `snap_to_lyrics` output (>=2 lines required)."""
    usable = [line for line in lines if str(line.get("text") or "").strip()]
    if len(usable) < 2:
        return ""
    return "\n".join(
        f"{format_lrc_time(float(line.get('startS') or 0.0))}{str(line['text']).strip()}"
        for line in usable
    )


# --------------------------------------------------------------------------- #
# Model path                                                                  #
# --------------------------------------------------------------------------- #
def load_model() -> Any:
    global MODEL
    if MODEL is not None:
        return MODEL
    with MODEL_LOAD_LOCK:
        if MODEL is None:
            from faster_whisper import WhisperModel  # imported lazily (heavy)

            MODEL = WhisperModel(
                MODEL_NAME,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                num_workers=1,
            )
    return MODEL


def _run_transcribe(audio_path: str, lyrics: str, vad: bool) -> tuple[list[dict[str, Any]], float]:
    model = load_model()
    with MODEL_LOCK:
        segments, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            vad_filter=vad,
            language=LANGUAGE,
            initial_prompt=(lyrics or "")[:1000] or None,
            beam_size=5,
        )
        words: list[dict[str, Any]] = []
        for segment in segments:
            for word in segment.words or []:
                text = (word.word or "").strip()
                if not text:
                    continue
                words.append({"word": text, "start": float(word.start), "end": float(word.end)})
    return words, float(getattr(info, "duration", 0.0) or 0.0)


def transcribe_words(audio_path: str, lyrics: str) -> tuple[list[dict[str, Any]], float]:
    """Transcribe with word timestamps.

    Silero VAD occasionally filters an entire sung track (zero segments), which
    yields no words and therefore no alignment. When that happens, retry once
    with VAD disabled so singing is still aligned.
    """
    words, duration = _run_transcribe(audio_path, lyrics, VAD)
    if not words and VAD:
        words, duration = _run_transcribe(audio_path, lyrics, False)
    return words, duration


def align(audio: bytes, lyrics: str) -> dict[str, Any]:
    fd, path = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(audio)
        recognized, duration = transcribe_words(path, lyrics)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    lines, words = snap_to_lyrics(recognized, lyrics)
    return {
        "ok": True,
        "engine": "faster-whisper",
        "model": MODEL_NAME,
        "durationS": round(duration, 3),
        "lines": lines,
        "words": words,
        "lrc": build_lrc(lines),
    }


# --------------------------------------------------------------------------- #
# HTTP                                                                        #
# --------------------------------------------------------------------------- #
def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("content-length", "0"))
    return handler.rfile.read(length) if length else b""


def _resolve_audio(handler: BaseHTTPRequestHandler, body: bytes) -> tuple[bytes, str]:
    ctype = (handler.headers.get("content-type") or "").lower()
    if ctype.startswith("application/json"):
        data = json.loads(body or b"{}")
        lyrics = str(data.get("lyrics") or "")
        url = data.get("url")
        if url:
            with urllib.request.urlopen(url, timeout=180) as resp:
                return resp.read(), lyrics
        audio_b64 = data.get("audio_b64") or data.get("audioB64")
        if audio_b64:
            return base64.b64decode(audio_b64), lyrics
        raise ValueError("url or audio_b64 required")
    lyrics_b64 = handler.headers.get("x-lyrics-b64", "")
    lyrics = base64.b64decode(lyrics_b64).decode("utf-8", "replace") if lyrics_b64 else ""
    return body, lyrics


class Handler(BaseHTTPRequestHandler):
    def _reply(self, obj: dict[str, Any], code: int = 200) -> None:
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply({"ok": True, "model": MODEL_NAME, "loaded": MODEL is not None})
        else:
            self._reply({"ok": False, "error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/align":
            self._reply({"ok": False, "error": "not found"}, 404)
            return
        # Gate before reading the body so an over-cap request never buffers the
        # track in memory. Reply 503 rather than queueing forever.
        if not INFLIGHT.acquire(timeout=QUEUE_WAIT_S):
            self._reply({"ok": False, "error": "busy"}, 503)
            return
        try:
            audio, lyrics = _resolve_audio(self, _read_body(self))
            if not audio:
                self._reply({"ok": False, "error": "empty audio"}, 400)
                return
            if not lyrics.strip():
                self._reply({"ok": False, "error": "lyrics required"}, 400)
                return
            self._reply(align(audio, lyrics))
        except Exception as exc:  # noqa: BLE001
            self._reply({"ok": False, "error": str(exc)}, 500)
        finally:
            INFLIGHT.release()

    def log_message(self, *args: Any) -> None:  # silence per-request logs
        pass


if __name__ == "__main__":
    print(f"[lrc-service] listening on 127.0.0.1:{PORT} (model={MODEL_NAME})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
