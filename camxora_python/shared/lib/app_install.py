"""First-launch / install timestamp for client diagnostics and setup notifications."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from shared.lib.app_paths import get_user_data_dir

_INSTALL_FILE = "install.json"
_cached: datetime | None = None


def _install_path() -> Path:
    return get_user_data_dir() / _INSTALL_FILE


def _parse_iso(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_or_seed_install_datetime() -> datetime:
    """Return the first-launch time, creating install.json on first call."""
    global _cached
    if _cached is not None:
        return _cached

    path = _install_path()
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            parsed = _parse_iso(str(payload.get("firstLaunchAt") or ""))
            if parsed is not None:
                _cached = parsed.astimezone()
                return _cached
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    now = datetime.now(timezone.utc).astimezone()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"firstLaunchAt": now.astimezone(timezone.utc).isoformat()}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
    _cached = now
    return _cached


def reset_install_datetime_cache_for_tests() -> None:
    global _cached
    _cached = None
