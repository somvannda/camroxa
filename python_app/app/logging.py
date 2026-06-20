from __future__ import annotations

from pathlib import Path
import sys
import threading

from .resources import python_app_dir

_inline_lock = threading.Lock()
_inline_last_len = 0


def log_path() -> Path:
    return python_app_dir() / "debug.log"


def log_line(msg: str) -> None:
    text = str(msg or "").strip()
    if not text:
        return
    end_inline()
    try:
        print(text, flush=True)
    except Exception:
        pass


def print_inline(msg: str) -> None:
    global _inline_last_len
    text = str(msg or "")
    if not text:
        return
    with _inline_lock:
        try:
            pad = ""
            try:
                pad_len = max(0, int(_inline_last_len) - len(text))
                if pad_len:
                    pad = " " * pad_len
            except Exception:
                pad = ""
            sys.stdout.write("\r" + text + pad)
            sys.stdout.flush()
            _inline_last_len = max(int(_inline_last_len), len(text))
        except Exception:
            pass


def end_inline() -> None:
    global _inline_last_len
    with _inline_lock:
        try:
            if int(_inline_last_len) > 0:
                sys.stdout.write("\n")
                sys.stdout.flush()
        except Exception:
            pass
        _inline_last_len = 0
    try:
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
