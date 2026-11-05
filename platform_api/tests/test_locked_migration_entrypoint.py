"""Deploy tooling must migrate through the advisory lock, not around it.

Production had two upgrade paths: the API startup runner (locked on
`pg_advisory_lock(782550187)`) and `camxora-production-remote.sh`, which ran
`alembic upgrade head` over SSH with no lock. Only the runner was serialized, so
a deploy and a booting worker could migrate at the same time â€” the overlap that
left `alembic_version = 178` recorded while its DDL was missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from platform_api.migrations import upgrade

DEPLOY_DIR = Path(__file__).resolve().parents[2] / "scripts" / "deploy"


def test_main_returns_zero_on_success() -> None:
    with patch.object(upgrade, "run_pending_migrations", AsyncMock(return_value=None)):
        assert upgrade.main() == 0


def test_main_returns_one_when_the_upgrade_fails() -> None:
    """A failed migration must fail the deploy, not be swallowed."""
    with patch.object(
        upgrade, "run_pending_migrations", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        assert upgrade.main() == 1


def test_remote_script_uses_the_locked_entrypoint() -> None:
    script = (DEPLOY_DIR / "camxora-production-remote.sh").read_text(encoding="utf-8")

    assert "python -m platform_api.migrations.upgrade" in script
    # The raw CLI would bypass the advisory lock the runner holds.
    assert "alembic upgrade head" not in script


def test_locked_entrypoint_reuses_the_runner() -> None:
    """One lock for both paths, or the serialization is fiction."""
    source = Path(upgrade.__file__).read_text(encoding="utf-8")
    assert "from platform_api.migrations.runner import run_pending_migrations" in source
