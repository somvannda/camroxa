"""Load `.env` files into os.environ before build_config resolves URLs."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
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
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_desktop_env() -> None:
    """Merge env files into os.environ (existing os.environ wins)."""
    module_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = [
        module_root / ".env",
        module_root / ".env.local",
        module_root / ".env.sandbox",
        module_root / ".env.production",
    ]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / ".env",
                exe_dir / ".env.sandbox",
                exe_dir / ".env.production",
            ]
        )
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            bundle = Path(meipass)
            candidates.extend(
                [
                    bundle / ".env",
                    bundle / ".env.sandbox",
                    bundle / ".env.production",
                ]
            )
        internal = exe_dir / "_internal"
        if internal.is_dir():
            candidates.extend(
                [
                    internal / ".env",
                    internal / ".env.sandbox",
                    internal / ".env.production",
                ]
            )

    candidates.append(Path.cwd() / ".env")

    merged: dict[str, str] = {}
    for path in candidates:
        if path.is_file():
            merged.update(_parse_env_file(path))

    for key, value in merged.items():
        if key not in os.environ:
            os.environ[key] = value
