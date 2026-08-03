"""Regression tests for run_entry.py's startup-import retry logic.

Seen in the wild: a bizarre, non-reproducible TypeError deep inside pydantic
on launch (most likely caused by antivirus/Windows Defender still touching
``_internal`` files). The app recovered on a later launch with no code
changes, which matches a transient, environment-triggered import failure
rather than a real bug in our code. The fix is a bounded retry with a clean
module cache and growing backoff around the fragile import-then-run chain,
instead of failing hard on the first attempt.
"""

from __future__ import annotations

import sys
import time

import run_entry


def test_run_desktop_with_retry_recovers_after_transient_import_failure(monkeypatch) -> None:
    attempts: list[int] = []

    def _fake_load_desktop_env() -> None:
        return None

    def _fake_run() -> int:
        attempts.append(1)
        if len(attempts) == 1:
            raise TypeError("'tuple_iterator' object does not support the context manager protocol")
        return 0

    fake_env_loader = type(sys)("shared.lib.env_loader")
    fake_env_loader.load_desktop_env = _fake_load_desktop_env
    fake_bootstrap = type(sys)("app.bootstrap")
    fake_bootstrap.run = _fake_run

    monkeypatch.setitem(sys.modules, "shared.lib.env_loader", fake_env_loader)
    monkeypatch.setitem(sys.modules, "app.bootstrap", fake_bootstrap)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    logged: list[tuple[int, int]] = []
    recovered: list[tuple[int, int]] = []
    monkeypatch.setattr(
        run_entry,
        "_write_early_crash_log",
        lambda attempt, max_attempts, exc: logged.append((attempt, max_attempts)),
    )
    monkeypatch.setattr(
        run_entry,
        "_write_early_recovery_log",
        lambda attempt, max_attempts: recovered.append((attempt, max_attempts)),
    )

    result = run_entry._run_desktop_with_retry(max_attempts=4)

    assert result == 0
    assert len(attempts) == 2
    assert logged == [(1, 4)]
    assert recovered == [(2, 4)]


def test_run_desktop_with_retry_survives_multiple_transient_failures(monkeypatch) -> None:
    attempts: list[int] = []

    def _fake_load_desktop_env() -> None:
        return None

    def _fake_run() -> int:
        attempts.append(1)
        if len(attempts) < 3:
            raise TypeError("'tuple_iterator' object does not support the context manager protocol")
        return 0

    fake_env_loader = type(sys)("shared.lib.env_loader")
    fake_env_loader.load_desktop_env = _fake_load_desktop_env
    fake_bootstrap = type(sys)("app.bootstrap")
    fake_bootstrap.run = _fake_run

    monkeypatch.setitem(sys.modules, "shared.lib.env_loader", fake_env_loader)
    monkeypatch.setitem(sys.modules, "app.bootstrap", fake_bootstrap)
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds, **_kwargs: sleeps.append(float(seconds)))
    monkeypatch.setattr(run_entry, "_write_early_crash_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_entry, "_write_early_recovery_log", lambda *_args, **_kwargs: None)

    result = run_entry._run_desktop_with_retry(max_attempts=4)

    assert result == 0
    assert len(attempts) == 3
    assert sleeps == [1.5, 3.0]


def test_run_desktop_with_retry_raises_after_exhausting_attempts(monkeypatch) -> None:
    def _fake_load_desktop_env() -> None:
        return None

    def _fake_run() -> int:
        raise TypeError("'tuple_iterator' object does not support the context manager protocol")

    fake_env_loader = type(sys)("shared.lib.env_loader")
    fake_env_loader.load_desktop_env = _fake_load_desktop_env
    fake_bootstrap = type(sys)("app.bootstrap")
    fake_bootstrap.run = _fake_run

    monkeypatch.setitem(sys.modules, "shared.lib.env_loader", fake_env_loader)
    monkeypatch.setitem(sys.modules, "app.bootstrap", fake_bootstrap)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_entry, "_write_early_crash_log", lambda *_args, **_kwargs: None)

    try:
        run_entry._run_desktop_with_retry(max_attempts=4)
    except TypeError as exc:
        assert "tuple_iterator" in str(exc)
    else:
        raise AssertionError("expected TypeError to propagate after exhausting retries")


def test_reset_partially_imported_modules_drops_only_new_modules(monkeypatch) -> None:
    baseline = set(sys.modules.keys())
    monkeypatch.setitem(sys.modules, "camxora_fake_new_module", type(sys)("camxora_fake_new_module"))

    assert "camxora_fake_new_module" in sys.modules
    run_entry._reset_partially_imported_modules(baseline)
    assert "camxora_fake_new_module" not in sys.modules
