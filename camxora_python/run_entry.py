"""PyInstaller entry — load env, then start Camxora desktop or visualizer."""

from __future__ import annotations

import sys


def _run_visualizer(argv: list[str]) -> int:
    """Re-enter as the GPU export CLI when launched from a frozen ExportJob."""
    sys.argv = [argv[0], *argv[2:]]
    from visualizer.main import main as visualizer_main

    return int(visualizer_main())


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--visualizer":
        return _run_visualizer(sys.argv)

    from shared.lib.env_loader import load_desktop_env

    load_desktop_env()
    from app.bootstrap import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
