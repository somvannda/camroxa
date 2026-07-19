"""Performance-safe application logger for camxora_python.

Design goals:
- Never block the UI thread on disk I/O
- Bounded memory (ring buffer) and bounded write queue (drop oldest under pressure)
- Optional UI subscribers via Qt queued signals
- Redaction before file/sync payloads
"""

from __future__ import annotations

import atexit
import re
import sys
import threading
import time
import traceback
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from shared.lib.app_paths import get_client_logs_dir

# Soft caps — keep logging cheap under load.
UI_RING_MAX = 5000
WRITE_QUEUE_MAX = 2000
FILE_RETENTION_DAYS = 14
MAX_FILE_BYTES = 25 * 1024 * 1024  # rotate within a day if huge
SYNC_MAX_LINES = 5000
SYNC_MAX_CHARS = 800_000


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40


_LEVEL_NAMES = {
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.WARN: "WARN",
    LogLevel.ERROR: "ERROR",
}

_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"),
    re.compile(r"(?i)\b(bearer\s+)\S+"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(refresh[_-]?token\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(password\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)\S+"),
)
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
_HTML_BODY_PATTERN = re.compile(
    r"(?is)(?:<!DOCTYPE\s+html|<html\b|<head\b|<body\b|<title\b|nginx/\d)",
)


def _looks_like_html_or_gateway_body(text: str) -> bool:
    sample = (text or "")[:800]
    if not sample:
        return False
    if _HTML_BODY_PATTERN.search(sample):
        return True
    # Long markup dumps from reverse proxies / error pages.
    if len(text) > 400 and sample.count("<") >= 3 and sample.count(">") >= 3:
        return True
    return False


def sanitize_error_body(text: str, *, status: int | None = None) -> str:
    """Replace HTML/gateway dumps with a short safe summary for logs and UI."""
    raw = str(text or "").strip()
    if not raw:
        return ""
    if not _looks_like_html_or_gateway_body(raw):
        return raw
    status_bit = f" HTTP {status}" if status is not None else ""
    return f"[omitted HTML/gateway error body{status_bit}, {len(raw)} chars]"


def redact_text(text: str) -> str:
    out = sanitize_error_body(str(text or ""))
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub(r"\1[REDACTED]", out)
    return _JWT_PATTERN.sub("[REDACTED]", out)


@dataclass(frozen=True, slots=True)
class LogRecord:
    ts: float
    level: LogLevel
    category: str
    message: str

    def format_line(self) -> str:
        stamp = datetime.fromtimestamp(self.ts, tz=timezone.utc).astimezone().strftime("%H:%M:%S")
        level = _LEVEL_NAMES.get(self.level, "INFO")
        cat = self.category or "app"
        return f"[{stamp}] {level:<5} [{cat}] {self.message}"


class _LogBus(QObject):
    """Qt signal bridge so UI updates stay on the GUI thread."""

    line_emitted = Signal(object)  # LogRecord
    cleared = Signal()


class AppLogger:
    """Process-wide logger singleton."""

    _instance: AppLogger | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._min_level = LogLevel.INFO
        self._records: deque[LogRecord] = deque(maxlen=UI_RING_MAX)
        self._lock = threading.RLock()
        self._bus = _LogBus()
        self._write_queue: deque[str] = deque()
        self._write_event = threading.Event()
        self._stop = threading.Event()
        self._dropped = 0
        self._last_prune_at = 0.0
        self._writer = threading.Thread(target=self._writer_loop, name="camxora-log-writer", daemon=True)
        self._writer.start()
        atexit.register(self.shutdown)

    @classmethod
    def instance(cls) -> AppLogger:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = AppLogger()
        return cls._instance

    @property
    def bus(self) -> _LogBus:
        return self._bus

    def set_min_level(self, level: LogLevel) -> None:
        self._min_level = level

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._dropped = 0
        self._bus.cleared.emit()

    def snapshot(self, *, max_lines: int = SYNC_MAX_LINES) -> list[LogRecord]:
        with self._lock:
            items = list(self._records)
        if max_lines > 0 and len(items) > max_lines:
            return items[-max_lines:]
        return items

    def snapshot_text(self, *, max_lines: int = SYNC_MAX_LINES, max_chars: int = SYNC_MAX_CHARS) -> str:
        lines = [redact_text(rec.format_line()) for rec in self.snapshot(max_lines=max_lines)]
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[-max_chars:]
            nl = text.find("\n")
            if nl >= 0:
                text = text[nl + 1 :]
        return text

    def debug(self, message: str, *, category: str = "app") -> None:
        self.log(LogLevel.DEBUG, message, category=category)

    def info(self, message: str, *, category: str = "app") -> None:
        self.log(LogLevel.INFO, message, category=category)

    def warn(self, message: str, *, category: str = "app") -> None:
        self.log(LogLevel.WARN, message, category=category)

    def error(self, message: str, *, category: str = "app", exc: BaseException | None = None) -> None:
        text = str(message or "")
        if exc is not None:
            detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            text = f"{text}\n{detail}".rstrip()
        self.log(LogLevel.ERROR, text, category=category)

    def log(self, level: LogLevel, message: str, *, category: str = "app") -> None:
        if int(level) < int(self._min_level):
            return
        clean = redact_text(str(message or "").replace("\r\n", "\n").strip())
        if not clean:
            return
        # Keep multi-line errors, but avoid pathological dumps.
        if len(clean) > 8000:
            clean = clean[:8000] + "…[truncated]"
        record = LogRecord(
            ts=time.time(),
            level=level,
            category=str(category or "app")[:40],
            message=clean,
        )
        with self._lock:
            self._records.append(record)
        # UI update is queued; never wait on subscribers.
        try:
            self._bus.line_emitted.emit(record)
        except Exception:
            pass
        line = record.format_line()
        self._enqueue_file_line(line)
        self._mirror_console(line)

    def _mirror_console(self, line: str) -> None:
        try:
            stream = sys.stderr if getattr(sys.stderr, "isatty", lambda: False)() else sys.stdout
            if stream is None or not getattr(stream, "isatty", lambda: False)():
                return
            print(line, file=stream, flush=True)
        except Exception:
            return

    def _enqueue_file_line(self, line: str) -> None:
        with self._lock:
            if len(self._write_queue) >= WRITE_QUEUE_MAX:
                # Drop oldest queued writes under pressure — never block callers.
                try:
                    self._write_queue.popleft()
                    self._dropped += 1
                except IndexError:
                    pass
            self._write_queue.append(line)
        self._write_event.set()

    def _writer_loop(self) -> None:
        while not self._stop.is_set():
            self._write_event.wait(timeout=0.5)
            self._write_event.clear()
            batch: list[str] = []
            with self._lock:
                while self._write_queue and len(batch) < 200:
                    batch.append(self._write_queue.popleft())
                dropped = self._dropped
                if dropped:
                    self._dropped = 0
            if dropped:
                batch.append(
                    f"[{datetime.now().strftime('%H:%M:%S')}] WARN  [log] dropped {dropped} queued line(s) under load"
                )
            if batch:
                self._append_file_lines(batch)

    def _append_file_lines(self, lines: list[str]) -> None:
        try:
            log_dir = get_client_logs_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            # Prune at most once per hour so file I/O stays off the hot path.
            now = time.time()
            if now - self._last_prune_at >= 3600:
                self._prune_old_files(log_dir)
                self._last_prune_at = now
            path = log_dir / f"camxora-{datetime.now().strftime('%Y%m%d')}.log"
            if path.is_file() and path.stat().st_size >= MAX_FILE_BYTES:
                rotated = log_dir / f"camxora-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
                try:
                    path.rename(rotated)
                except OSError:
                    pass
            with path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write("\n".join(lines))
                handle.write("\n")
        except Exception:
            # Logging must never raise into app code.
            return

    def _prune_old_files(self, log_dir: Path) -> None:
        try:
            cutoff = time.time() - (FILE_RETENTION_DAYS * 86400)
            for path in log_dir.glob("camxora-*.log"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
                except OSError:
                    continue
        except Exception:
            return

    def shutdown(self) -> None:
        self._stop.set()
        self._write_event.set()
        try:
            self._writer.join(timeout=1.0)
        except Exception:
            pass


def get_app_logger() -> AppLogger:
    return AppLogger.instance()


def log_info(message: str, *, category: str = "app") -> None:
    get_app_logger().info(message, category=category)


def log_warn(message: str, *, category: str = "app") -> None:
    get_app_logger().warn(message, category=category)


def log_error(message: str, *, category: str = "app", exc: BaseException | None = None) -> None:
    get_app_logger().error(message, category=category, exc=exc)


def log_debug(message: str, *, category: str = "app") -> None:
    get_app_logger().debug(message, category=category)
