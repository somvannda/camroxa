"""PyInstaller entry — load env, then start Camxora desktop or visualizer."""

from __future__ import annotations

import sys


def _run_visualizer(argv: list[str]) -> int:
    """Re-enter as the GPU export CLI when launched from a frozen ExportJob."""
    from visualizer.main import run_visualizer_argv

    return int(run_visualizer_argv([argv[0], *argv[2:]]))


def _early_crash_log_paths() -> list[str]:
    """Candidate paths for the early-startup crash log (best-effort)."""
    import os

    paths: list[str] = []
    for base in (
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("USERPROFILE") and os.path.join(os.environ["USERPROFILE"], "AppData", "Local"),
        os.path.expanduser("~"),
    ):
        if not base:
            continue
        paths.append(os.path.join(base, "Camxora", "logs", "early-startup-crash.log"))
    # Also next to the frozen executable — survives even when the user profile
    # path is wrong/unwritable (the cross-machine LOCALAPPDATA class of bug).
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if exe_dir:
            paths.append(os.path.join(exe_dir, "early-startup-crash.log"))
    except Exception:
        pass
    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for path in paths:
        key = path.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


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

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"\n[{stamp}] startup import attempt {attempt}/{max_attempts} failed\n",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    ]
    payload = "".join(lines)
    for log_path in _early_crash_log_paths():
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(payload)
            return
        except Exception:
            continue


def _write_early_recovery_log(attempt: int, max_attempts: int) -> None:
    """Record that a later retry recovered after an earlier import failure."""
    import os
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = (
        f"\n[{stamp}] startup import recovered on attempt {attempt}/{max_attempts}\n"
    )
    for log_path in _early_crash_log_paths():
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(payload)
            return
        except Exception:
            continue


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


def _run_desktop_with_retry(max_attempts: int = 4) -> int:
    """Import + launch the desktop app, retrying on transient import failures.

    Seen in the wild on launch (especially right after a fresh install, or
    when Defender is still scanning ``_internal``): a bizarre, non-reproducible
    TypeError deep inside pydantic while importing our module tree
    (``'tuple_iterator' object does not support the context manager protocol``).
    A short backoff with a clean module cache has cleared it every time
    observed. We retry a few times (not just once) because a single 1.5s
    pause is sometimes not enough for the scanner to release the file. If it
    keeps failing, log every attempt and re-raise so the failure is still
    visible.
    """
    import gc
    import time

    baseline_modules = set(sys.modules.keys())
    last_exc: BaseException = RuntimeError("unreachable")
    failed_attempts = 0
    for attempt in range(1, max_attempts + 1):
        try:
            _reset_partially_imported_modules(baseline_modules)
            from shared.lib.env_loader import load_desktop_env

            load_desktop_env()
            from app.bootstrap import run

            if failed_attempts:
                _write_early_recovery_log(attempt, max_attempts)
            return run()
        except BaseException as exc:  # noqa: BLE001 - deliberately broad: this is the last line of defense
            last_exc = exc
            failed_attempts += 1
            _write_early_crash_log(attempt, max_attempts, exc)
            if attempt >= max_attempts:
                raise
            # Growing backoff: give antivirus / file locks more time to settle
            # before the next clean import attempt.
            gc.collect()
            time.sleep(1.5 * attempt)
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
