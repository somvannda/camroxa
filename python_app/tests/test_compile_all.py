"""
Property 8: Compilation Validity

For any .py file in the python_app/ directory tree, running py_compile
should succeed without errors.

**Validates: Requirements 7.5**
"""

import py_compile
from pathlib import Path

PYTHON_APP = Path(__file__).resolve().parent.parent


def test_all_python_files_compile():
    """Every .py file under python_app/ must compile without errors."""
    failures = []
    for py_file in PYTHON_APP.rglob("*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"  {py_file.relative_to(PYTHON_APP)}: {exc}")
    assert not failures, "Compilation failures:\n" + "\n".join(failures)
