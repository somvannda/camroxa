"""Helpers so export crash detail reaches the diagnostics ring buffer."""

from __future__ import annotations

import re
from pathlib import Path

# Progress lines worth persisting during hangs (Mode B: stuck on Analyzing…).
_MILESTONE_RE = re.compile(
    r"(analyz|audio analysis|cache hit|from cache|preparing encoder|encoder started|"
    r"ffmpeg|nvenc|x264|loading audio|moderngl|opengl|readback|failed|traceback|"
    r"error|cuda|cannot create context|out of memory|vram)",
    re.IGNORECASE,
)


def append_export_event_line(lines: list[str], event: dict | None, *, max_lines: int = 40) -> None:
    """Keep a short rolling tail of failed/log lines from MG_EVENT / stdout."""
    if not isinstance(event, dict):
        return
    status = str(event.get("status") or "").strip().lower()
    message = str(event.get("message") or "").strip()
    if not message:
        return
    if status not in {"failed", "log", "error", "warning"}:
        return
    # Ignore pygame/SDL banner noise that appears when a cancelled worker dies.
    low = message.lower()
    if "pygame" in low and "hello from the pygame community" in low:
        return
    if lines and lines[-1] == message:
        return
    lines.append(message)
    if len(lines) > max_lines:
        del lines[:-max_lines]


def tail_export_error_detail(lines: list[str], *, max_lines: int = 12) -> str:
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])


def format_export_failure_message(
    *,
    exit_code: int,
    mp3_path: str,
    detail: str = "",
    backend_used: str = "",
) -> str:
    name = Path(str(mp3_path or "")).name or "track"
    head = f"Export failed with exit code {exit_code} for {name}."
    extras: list[str] = []
    backend = str(backend_used or "").strip()
    if backend:
        extras.append(f"backend={backend}")
    body = str(detail or "").strip()
    if extras:
        head = f"{head} ({', '.join(extras)})"
    if not body:
        return head
    return f"{head}\n{body}"


def is_export_milestone_message(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    return bool(_MILESTONE_RE.search(text))
