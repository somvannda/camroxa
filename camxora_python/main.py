"""Camxora desktop application entry point.

Usage:
  python main.py              # local API (localhost:8000)
  python main.py local
  python main.py sandbox
  python main.py production
  python main.py --env sandbox
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    from shared.services.runtime_target import apply_cli_runtime_target

    target, remaining = apply_cli_runtime_target(args)
    # Keep Qt / QApplication argv clean (no bare "sandbox" positional).
    sys.argv = [sys.argv[0], *remaining]
    if target:
        print(f"[app] Runtime target: {target}", flush=True)

    from app.bootstrap import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
