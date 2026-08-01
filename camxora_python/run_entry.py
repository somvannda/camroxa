"""PyInstaller entry — load env, then start Camxora desktop or visualizer."""

from __future__ import annotations

import sys


def _run_visualizer(argv: list[str]) -> int:
    """Re-enter as the GPU export CLI when launched from a frozen ExportJob."""
    from visualizer.main import run_visualizer_argv

    return int(run_visualizer_argv([argv[0], *argv[2:]]))


def _write_early_crash_log(attempt: int, max_attempts: int, exc: BaseException) -> None:
    """Best-effort crash log for failures during the initial import chain.

    Uses only stdlib so it can't itself fail from a half-imported app module
    (the failure we're logging can happen mid-import of our own code, e.g.
    while importing shared.models.platform). Written next to the normal
    AppLogger output so it's easy to find alongside other client logs.
    """
    import os
    import traceback
    from datetime import datetime, timezone

    try:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        log_dir = os.path.join(base, "Camxora", "logs")
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(os.path.join(log_dir, "early-startup-crash.log"), "a", encoding="utf-8") as fh:
            fh.write(f"\n[{stamp}] startup import attempt {attempt}/{max_attempts} failed\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=fh)
    except Exception:
        pass


def _reset_partially_imported_modules(baseline: set[str]) -> None:
    """Drop any module imported since `baseline` before retrying.

    A failed import can leave partially-initialized modules in sys.modules
    (e.g. a class body that raised halfway through). Re-importing without
    clearing these would just return the same broken module object instead
    of giving the retry a genuinely fresh attempt.
    """
    for name in list(sys.modules.keys()):
        if name not in baseline:
            sys.modules.pop(name, None)


def _run_desktop_with_retry(max_attempts: int = 2) -> int:
    """Import + launch the desktop app, retrying once on a transient failure.

    Seen in the wild on the very first launch right after a fresh install:
    a bizarre, non-reproducible error deep inside a third-party dependency
    (pydantic) while importing our module tree — most likely caused by
    antivirus/Windows Defender real-time scanning still touching the
    freshly-extracted install files. A short retry with a clean module
    cache has cleared it every time observed. If it keeps failing, log it
    and re-raise so the failure is still visible.
    """
    import time

    baseline_modules = set(sys.modules.keys())
    last_exc: BaseException = RuntimeError("unreachable")
    for attempt in range(1, max_attempts + 1):
        try:
            _reset_partially_imported_modules(baseline_modules)
            from shared.lib.env_loader import load_desktop_env

            load_desktop_env()
            from app.bootstrap import run

            return run()
        except BaseException as exc:  # noqa: BLE001 - deliberately broad: this is the last line of defense
            last_exc = exc
            _write_early_crash_log(attempt, max_attempts, exc)
            if attempt >= max_attempts:
                raise
            time.sleep(1.5)
    raise last_exc


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--visualizer":
        return _run_visualizer(sys.argv)

    if len(sys.argv) > 1 and sys.argv[1] == "--visualizer-daemon":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        from visualizer.daemon import run_daemon_loop

        return int(run_daemon_loop())

    return _run_desktop_with_retry()


if __name__ == "__main__":
    raise SystemExit(main())
