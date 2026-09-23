"""Guardrails: no bare Windows subprocess launches that flash a console."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from shared.lib.subprocess_utils import no_window_kwargs


ROOT = Path(__file__).resolve().parents[1]

# Direct subprocess APIs that must go through shared.lib.subprocess_utils.
_FORBIDDEN_ATTRS = frozenset({"Popen", "run", "call", "check_output", "check_call"})

# Modules allowed to define wrappers or test doubles.
_ALLOWLIST_RELATIVE = frozenset(
    {
        "shared/lib/subprocess_utils.py",
        "tests/test_subprocess_console_guard.py",
        "tests/test_software_update_installer.py",
    }
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if (
            rel.startswith("build/")
            or rel.startswith("dist/")
            or "/__pycache__/" in f"/{rel}/"
        ):
            continue
        files.append(path)
    return files


def test_no_window_kwargs_sets_create_no_window_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shared.lib.subprocess_utils.sys.platform", "win32")
    kwargs = no_window_kwargs()
    assert "creationflags" in kwargs
    assert kwargs["creationflags"] != 0
    assert "startupinfo" in kwargs


def test_no_bare_subprocess_console_launches() -> None:
    """Fail CI if someone adds subprocess.Popen/run without the hidden helpers."""
    offenders: list[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in _ALLOWLIST_RELATIVE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # subprocess.Popen(...) / subprocess.run(...)
            if (
                isinstance(func, ast.Attribute)
                and func.attr in _FORBIDDEN_ATTRS
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            ):
                offenders.append(f"{rel}:{node.lineno} subprocess.{func.attr}(...)")
                continue
            # from subprocess import Popen; Popen(...)  — only if imported from subprocess
            if isinstance(func, ast.Name) and func.id in _FORBIDDEN_ATTRS:
                # Skip common app entrypoints named run()
                if func.id == "run":
                    continue
                offenders.append(f"{rel}:{node.lineno} {func.id}(...)")

    assert not offenders, (
        "Bare subprocess launches can flash a Windows console. "
        "Use shared.lib.subprocess_utils.run_hidden / popen_hidden / check_output_hidden:\n"
        + "\n".join(f"  - {item}" for item in offenders)
    )
