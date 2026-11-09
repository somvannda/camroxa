"""In-process record of the post-migration schema assertions.

`verify_schema_assertions()` runs at startup, right after alembic upgrades. Its
result used to go only to the log: production sat at `alembic_version = 178`
with `credit_transactions.reason` still `varchar(100)` while `/health` reported
"healthy", and nobody noticed until an admin adjustment 500'd.

The runner records the outcome here so `/health` can report it. This is a status
holder, not a cache: each process records its own result during startup, and a
worker that never ran migrations reports `checked: false`.
"""

from __future__ import annotations

from typing import Any

_checked = False
_failures: list[str] = []


def record(failures: list[str] | None) -> None:
    """Store the result of a schema assertion pass."""
    global _checked, _failures
    _checked = True
    _failures = list(failures or [])


def reset() -> None:
    """Clear the record (tests, and a database reset in tooling)."""
    global _checked, _failures
    _checked = False
    _failures = []


def snapshot() -> dict[str, Any]:
    """Public shape for `/health`."""
    return {
        "checked": _checked,
        "ok": not _failures,
        "failures": list(_failures),
    }
