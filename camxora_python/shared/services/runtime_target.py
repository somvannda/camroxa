"""CLI / process runtime target for local desktop runs (`python main.py sandbox`)."""

from __future__ import annotations

import os
from pathlib import Path

_TARGET_ALIASES = {
    "local": "local",
    "dev": "local",
    "development": "local",
    "sandbox": "sandbox",
    "sb": "sandbox",
    "production": "production",
    "prod": "production",
}

_DEFAULTS = {
    "local": {
        "CAMXORA_BUILD_ENV": "development",
        "CAMXORA_API_BASE_URL": "http://localhost:8000/api/v1",
        "CAMXORA_PORTAL_BASE_URL": "http://localhost:3001",
    },
    "sandbox": {
        "CAMXORA_BUILD_ENV": "sandbox",
        "CAMXORA_API_BASE_URL": "https://api.sandbox.camxora.com/api/v1",
        "CAMXORA_PORTAL_BASE_URL": "https://app.sandbox.camxora.com",
    },
    "production": {
        "CAMXORA_BUILD_ENV": "production",
        "CAMXORA_API_BASE_URL": "https://api.camxora.com/api/v1",
        "CAMXORA_PORTAL_BASE_URL": "https://app.camxora.com",
    },
}


def _module_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.lower().startswith("export "):
            stripped = stripped[7:].strip()
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def normalize_runtime_target(value: str | None) -> str | None:
    key = str(value or "").strip().lower()
    if not key:
        return None
    return _TARGET_ALIASES.get(key)


def apply_runtime_target(target: str) -> str:
    """Force process env for a runtime target. Returns normalized target name."""
    normalized = normalize_runtime_target(target)
    if normalized is None:
        raise ValueError(
            f"Unknown runtime target {target!r}. Use: local | sandbox | production"
        )

    values = dict(_DEFAULTS[normalized])
    # Prefer checked-in / local release env files for sandbox/production URLs.
    if normalized == "sandbox":
        values.update(_read_env_file(_module_root() / ".env.sandbox"))
    elif normalized == "production":
        values.update(_read_env_file(_module_root() / ".env.production"))

    for key in ("CAMXORA_BUILD_ENV", "CAMXORA_API_BASE_URL", "CAMXORA_PORTAL_BASE_URL"):
        if key in values and str(values[key]).strip():
            os.environ[key] = str(values[key]).strip().rstrip("/")
    # Ensure build env matches the requested target even if the file says otherwise.
    os.environ["CAMXORA_BUILD_ENV"] = _DEFAULTS[normalized]["CAMXORA_BUILD_ENV"]
    return normalized


def consume_runtime_target_argv(argv: list[str]) -> tuple[str | None, list[str]]:
    """Parse `local|sandbox|production` or `--env <name>` from argv.

    Returns (target_or_none, remaining_argv). Does not mutate os.environ.
    """
    if not argv:
        return None, []

    remaining = list(argv)
    target: str | None = None

    # --env sandbox / --env=sandbox
    i = 0
    while i < len(remaining):
        arg = remaining[i]
        if arg in {"--env", "-e"} and i + 1 < len(remaining):
            target = remaining[i + 1]
            del remaining[i : i + 2]
            break
        if arg.startswith("--env="):
            target = arg.split("=", 1)[1]
            del remaining[i]
            break
        i += 1

    # positional: python main.py sandbox
    if target is None and remaining:
        candidate = normalize_runtime_target(remaining[0])
        if candidate is not None:
            target = remaining[0]
            del remaining[0]

    normalized = normalize_runtime_target(target) if target else None
    return normalized, remaining


def apply_cli_runtime_target(argv: list[str]) -> tuple[str | None, list[str]]:
    """Apply CLI target to os.environ and return (target, remaining_argv)."""
    target, remaining = consume_runtime_target_argv(argv)
    if target:
        apply_runtime_target(target)
    return target, remaining
