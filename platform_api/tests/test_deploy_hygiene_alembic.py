"""Deploy scripts must not bypass the migration advisory lock.

`camxora-production-remote.sh` used to run the raw Alembic CLI while the API
startup runner held `pg_advisory_lock(782550187)`, so a deploy and a booting
worker could upgrade at the same time. Both paths now go through
`platform_api.migrations.upgrade`; this check keeps the raw CLI from creeping
back into a deploy script.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "scripts" / "deploy"


@pytest.fixture(scope="module")
def hygiene():
    path = DEPLOY_DIR / "check_deploy_hygiene.py"
    spec = importlib.util.spec_from_file_location("deploy_hygiene", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _scan(hygiene, tmp_path: Path, body: str):
    script = tmp_path / "deploy_thing.py"
    script.write_text(body, encoding="utf-8")
    return hygiene.scan_raw_alembic([script])


def test_detects_inline_chained_upgrade(hygiene, tmp_path: Path) -> None:
    found = _scan(
        hygiene,
        tmp_path,
        'run(\'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head\')\n',
    )
    assert len(found) == 1


def test_detects_a_bare_shell_line(hygiene, tmp_path: Path) -> None:
    found = _scan(hygiene, tmp_path, "alembic upgrade head\n")
    assert len(found) == 1


def test_detects_a_stamp(hygiene, tmp_path: Path) -> None:
    """A stamp advances the version without applying DDL â€” the 178 failure mode."""
    found = _scan(hygiene, tmp_path, 'x && alembic stamp 116_credits_only_v3 || true\n')
    assert len(found) == 1


def test_ignores_comments_and_docstrings(hygiene, tmp_path: Path) -> None:
    found = _scan(
        hygiene,
        tmp_path,
        '"""Run migrations without a full alembic upgrade."""\n'
        "# 2) Alembic upgrade, then restart API.\n"
        "# Does not run alembic upgrade head.\n"
        "journalctl | grep -E 'Skipping leftover Alembic|alembic upgrade' || true\n",
    )
    assert found == []


def test_ignores_the_locked_entrypoint(hygiene, tmp_path: Path) -> None:
    found = _scan(
        hygiene,
        tmp_path,
        "platform_api/.venv/bin/python -m platform_api.migrations.upgrade\n",
    )
    assert found == []


def test_every_current_deploy_script_is_allowlisted(hygiene) -> None:
    """Existing offenders stay tolerated so --strict stays actionable."""
    blocking = [
        finding
        for finding in hygiene.scan_raw_alembic(hygiene.default_targets())
        if finding.path.name not in hygiene.KNOWN_LEGACY_RAW_ALEMBIC
    ]
    assert blocking == []
