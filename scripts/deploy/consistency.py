"""Deploy consistency guard.

Refuses a ``platform_api`` deploy when the local repo's migration set does not
cover the target database's applied revision — the exact situation that earlier
left production code behind its DB (a deploy from a branch older than the DB head
reinstalled ``platform_api`` without the migration files, and ``alembic upgrade``
then failed).

Also flags multiple migration heads. Runs before the source is uploaded so a
stale worktree/branch cannot silently clobber a newer deployment.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "platform_api" / "migrations" / "versions"

_REVISION_RE = re.compile(
    r'^revision(?:\s*:\s*[^=]+)?\s*=\s*["\']([^"\']+)["\']', re.MULTILINE
)
_DOWN_RE = re.compile(r'^down_revision(?:\s*:\s*[^=]+)?\s*=\s*(.+)$', re.MULTILINE)


def _parse_revision(text: str) -> str | None:
    match = _REVISION_RE.search(text)
    return match.group(1) if match else None


def _parse_down_revisions(text: str) -> set[str]:
    match = _DOWN_RE.search(text)
    if not match:
        return set()
    raw = match.group(1).strip()
    return set(re.findall(r'["\']([^"\']+)["\']', raw))


def local_revision_map() -> dict[str, set[str]]:
    """Map each local migration revision to the revisions it descends from."""
    revisions: dict[str, set[str]] = {}
    for path in MIGRATIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        revision = _parse_revision(text)
        if revision is None:
            continue
        revisions[revision] = _parse_down_revisions(text)
    return revisions


def local_heads(revisions: dict[str, set[str]] | None = None) -> set[str]:
    """Revisions that no other revision descends from (alembic heads)."""
    revisions = revisions if revisions is not None else local_revision_map()
    referenced: set[str] = set()
    for downs in revisions.values():
        referenced.update(downs)
    return set(revisions) - referenced


def remote_db_revision(client: Any, db: str = "camxora_platform") -> str:
    """The target DB's applied alembic revision ('' when uninitialised)."""
    cmd = (
        "sudo -u postgres psql -d "
        f"{db} -t -A -c 'SELECT version_num FROM alembic_version;'"
    )
    _stdin, stdout, _stderr = client.exec_command(cmd)
    return stdout.read().decode("utf-8", errors="replace").strip()


def check_consistency(client: Any, db: str = "camxora_platform") -> None:
    """Raise ``SystemExit`` when the local repo cannot safely deploy to ``db``."""
    revisions = local_revision_map()
    heads = local_heads(revisions)
    if len(heads) > 1:
        raise SystemExit(
            "Refusing deploy: multiple migration heads in this worktree: "
            + ", ".join(sorted(heads))
            + ". Merge/rebase so there is a single head."
        )

    db_revision = remote_db_revision(client, db)
    if not db_revision:
        print(f"[consistency] {db}: no alembic_version yet (fresh DB) — OK")
        return

    if db_revision not in revisions:
        raise SystemExit(
            f"Refusing deploy: target {db} is at revision '{db_revision}', which this "
            "worktree's migrations do not contain. This worktree is behind — rebase onto "
            "current origin/main (or the branch that owns that migration) before deploying, "
            "otherwise the DB/code will diverge."
        )

    print(
        f"[consistency] {db}: db={db_revision} present locally "
        f"(local head(s): {', '.join(sorted(heads))}) — OK"
    )
