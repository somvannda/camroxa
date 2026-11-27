#!/usr/bin/env python3
"""Keep live credentials when a deploy regenerates platform_api/.env.

The production install script writes ``platform_api/.env`` from scratch on every
deploy, using only the keys exported by the operator's secrets file.  When that
file does not carry an integration's credentials, the generated file gets an
empty value and the live feature breaks silently.  That is what took Google
sign-in down on 2026-11-26: the secrets file had no Google client id/secret, so
the next deploy wrote ``PLATFORM_GOOGLE_CLIENT_ID=`` over working credentials.

This helper is run right after the new ``.env`` is written: for each listed key
whose new value is empty (or missing), the previous non-empty value is kept.
An explicitly supplied value always wins, so rotating a credential still works.
Disable an integration with its own flag (for example
``PLATFORM_POSTFORME_ENABLED=false``) rather than by blanking its credential.
"""

from __future__ import annotations

import argparse
import os
import stat
import tempfile
from pathlib import Path

DEFAULT_KEYS = (
    "PLATFORM_GOOGLE_CLIENT_ID",
    "PLATFORM_GOOGLE_CLIENT_SECRET",
    "PLATFORM_POSTFORME_API_KEY",
    "PLATFORM_POSTFORME_WEBHOOK_SECRET",
)


def read_env(path: Path) -> dict[str, str]:
    """Parse simple ``KEY=value`` lines, ignoring comments and blanks."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def preserve_missing(
    previous: Path, current: Path, keys: tuple[str, ...] = DEFAULT_KEYS
) -> list[str]:
    """Restore previous non-empty values for keys empty/absent in ``current``.

    Returns the keys that were preserved, in the order given.
    """
    old = read_env(previous)
    wanted = set(keys)
    lines = current.read_text(encoding="utf-8", errors="replace").splitlines()
    preserved: list[str] = []
    present: set[str] = set()

    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key not in wanted:
            continue
        present.add(key)
        if not value and old.get(key):
            lines[index] = f"{key}={old[key]}"
            preserved.append(key)

    appended = False
    for key in keys:
        if key not in present and old.get(key):
            lines.append(f"{key}={old[key]}")
            preserved.append(key)
            appended = True

    if preserved:
        text = "\n".join(lines) + "\n"
        mode = stat.S_IMODE(current.stat().st_mode)
        fd, tmp = tempfile.mkstemp(dir=str(current.parent), prefix=".env-preserve.")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, current)
    return preserved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", required=True, help="pre-deploy .env snapshot")
    parser.add_argument("--current", required=True, help="newly generated .env")
    parser.add_argument(
        "keys",
        nargs="*",
        default=list(DEFAULT_KEYS),
        help="keys to preserve (defaults to the credential set)",
    )
    args = parser.parse_args(argv)

    preserved = preserve_missing(
        Path(args.previous), Path(args.current), tuple(args.keys)
    )
    for key in preserved:
        print(f"kept previous {key} (deploy secrets did not provide one)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
