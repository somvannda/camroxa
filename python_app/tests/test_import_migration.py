"""
Property 2: Import Path Migration Completeness

Scans all .py files in the python_app directory and asserts that zero imports
reference the old paths: app.style_helper, app.widget_factory, or
app.footer_controller.

Feature: enterprise-architecture-refactor, Property 2: Import Path Migration Completeness
Validates: Requirements 1.3, 2.5
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Root of the python_app package
PYTHON_APP_ROOT = Path(__file__).resolve().parent.parent

# Old import paths that should no longer appear anywhere
FORBIDDEN_OLD_PATHS = {
    "app.style_helper",
    "app.widget_factory",
    "app.footer_controller",
}


def _collect_all_py_files() -> list[Path]:
    """Collect all .py files under python_app/, excluding __pycache__ and .env."""
    py_files = []
    for py_file in PYTHON_APP_ROOT.rglob("*.py"):
        # Skip cache directories and test file itself
        if "__pycache__" in str(py_file):
            continue
        py_files.append(py_file)
    return sorted(py_files)


def _extract_import_paths(filepath: Path) -> list[str]:
    """Parse a Python file's AST and return all imported module paths."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    import_paths = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_paths.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                import_paths.append(node.module)
    return import_paths


def _check_file_for_old_imports(filepath: Path) -> list[str]:
    """Check a single file for forbidden old import paths.

    Returns a list of violation descriptions.
    """
    violations = []
    import_paths = _extract_import_paths(filepath)
    for imp in import_paths:
        for forbidden in FORBIDDEN_OLD_PATHS:
            # Match exact module or submodule (e.g. "app.style_helper" or "app.style_helper.something")
            if imp == forbidden or imp.startswith(forbidden + "."):
                rel_path = filepath.relative_to(PYTHON_APP_ROOT)
                violations.append(
                    f"{rel_path}: imports '{imp}' (should use views.helpers.* instead)"
                )
    return violations


# ---------------------------------------------------------------------------
# Property-Based Test
# ---------------------------------------------------------------------------

ALL_PY_FILES = _collect_all_py_files()


@given(file_index=st.integers(min_value=0, max_value=max(len(ALL_PY_FILES) - 1, 0)))
@settings(
    max_examples=100,
    deadline=None,  # this property does per-example file I/O; timing is not under test
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_no_old_import_paths_property(file_index: int) -> None:
    """**Validates: Requirements 1.3, 2.5**

    Property 2: Import Path Migration Completeness

    For any Python source file in the project, it should contain zero import
    references to the old paths app.style_helper, app.widget_factory, or
    app.footer_controller.
    """
    if not ALL_PY_FILES:
        pytest.skip("No Python files found to scan")

    filepath = ALL_PY_FILES[file_index]
    violations = _check_file_for_old_imports(filepath)
    assert not violations, (
        f"Old import path(s) found:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Exhaustive Test (covers every file deterministically)
# ---------------------------------------------------------------------------


def test_no_old_import_paths_exhaustive() -> None:
    """Exhaustive scan: every .py file must have zero references to old import paths.

    **Validates: Requirements 1.3, 2.5**
    """
    all_violations = []
    for filepath in ALL_PY_FILES:
        all_violations.extend(_check_file_for_old_imports(filepath))

    assert not all_violations, (
        f"Found {len(all_violations)} old import path reference(s):\n"
        + "\n".join(all_violations)
    )
