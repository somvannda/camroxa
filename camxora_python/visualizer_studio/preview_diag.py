"""Always-on preview OpenGL diagnostics for installer / support bundles.

Mirrors ``visualizer.audio._audio_diag``: write to
``%LOCALAPPDATA%\\Camxora\\logs\\preview-gl-diag.log`` (writable on frozen
installs) and mirror important lines into the daily ``camxora-*.log`` via
AppLogger. Never block or raise into the preview paint path.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

DiagLevel = Literal["debug", "info", "warn", "error"]

_APP_MIRROR_LEVELS = frozenset({"info", "warn", "error"})
_WRITE_LOCK = threading.Lock()


def preview_gl_diag_log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "Camxora" / "logs" / "preview-gl-diag.log"


def write_preview_gl_diag(
    message: str,
    *,
    level: DiagLevel = "info",
    mirror_app_log: bool | None = None,
) -> None:
    """Append one diagnostic line. Never raises."""
    text = str(message or "").strip()
    if not text:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level_key = str(level or "info").strip().lower()
    if level_key not in {"debug", "info", "warn", "error"}:
        level_key = "info"
    line = f"[{stamp}] {level_key.upper():<5} {text}"

    try:
        print(f"[preview-gl-diag] {text}", flush=True)
    except Exception:
        pass

    try:
        path = preview_gl_diag_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(line + "\n")
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
    except Exception:
        pass

    should_mirror = mirror_app_log if mirror_app_log is not None else level_key in _APP_MIRROR_LEVELS
    if not should_mirror:
        return
    try:
        from shared.services.app_logger import log_debug, log_error, log_info, log_warn

        if level_key == "error":
            log_error(text, category="preview-gl")
        elif level_key == "warn":
            log_warn(text, category="preview-gl")
        elif level_key == "debug":
            log_debug(text, category="preview-gl")
        else:
            log_info(text, category="preview-gl")
    except Exception:
        return


def format_gl_context_info(ctx: object | None) -> dict[str, str]:
    """Best-effort ModernGL / OpenGL identity fields for diagnostics JSON."""
    out: dict[str, str] = {
        "frozen": str(bool(getattr(sys, "frozen", False))),
    }
    if ctx is None:
        return out
    try:
        version_code = getattr(ctx, "version_code", None)
        if version_code is not None:
            out["versionCode"] = str(version_code)
    except Exception:
        pass
    try:
        info = getattr(ctx, "info", None)
        if isinstance(info, dict):
            for key in ("GL_VENDOR", "GL_RENDERER", "GL_VERSION", "GL_SHADING_LANGUAGE_VERSION"):
                value = info.get(key)
                if value is not None:
                    out[key] = str(value)
    except Exception:
        pass
    return out
