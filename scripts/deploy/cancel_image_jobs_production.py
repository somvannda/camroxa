#!/usr/bin/env python3
"""Production: cancel (soft) image_jobs across all users.

Sets status='cancelled' on every image_jobs row whose status is in the selected
set (default: failed,pending,running). Cancelled rows are terminal: they are not
claimed by the runner and not picked up by the failed-job auto-retry requeue.

Rows are kept (no deletes) and a JSON snapshot of the affected rows is written
remotely and pulled locally for rollback. Dry-run by default; pass --apply to
write. Refuses non-production hosts.

Usage:
    python scripts/deploy/cancel_image_jobs_production.py                 # dry-run
    python scripts/deploy/cancel_image_jobs_production.py --apply
    python scripts/deploy/cancel_image_jobs_production.py --apply --statuses pending,running
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

REMOTE_PY = r'''
import asyncio
import json
import os
import sys
from pathlib import Path

os.chdir("/opt/camxora/repo")
sys.path.insert(0, "/opt/camxora/repo")
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
env_path = Path("/opt/camxora/repo/platform_api/.env")
if env_path.is_file():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

import asyncpg
from platform_api.config import get_settings, is_production

APPLY = os.environ.get("CX_APPLY") == "1"
ALLOWED = {"failed", "pending", "running", "cancelled", "success"}
STATUSES = [
    s.strip()
    for s in os.environ.get("CX_STATUSES", "failed,pending,running").split(",")
    if s.strip()
]
if not STATUSES:
    raise SystemExit("no statuses selected")
bad = [s for s in STATUSES if s not in ALLOWED]
if bad:
    raise SystemExit(f"invalid statuses: {bad}")
if "success" in STATUSES and os.environ.get("CX_ALLOW_SUCCESS") != "1":
    raise SystemExit("refusing to cancel success rows without CX_ALLOW_SUCCESS=1")

SNAPSHOT_PATH = "/opt/camxora/tmp/cancelled_image_jobs_snapshot.json"


async def status_counts(pool) -> dict:
    rows = await pool.fetch(
        "SELECT status, count(*) AS cnt FROM image_jobs GROUP BY status ORDER BY status"
    )
    return {r["status"]: int(r["cnt"]) for r in rows}


async def main() -> int:
    settings = get_settings()
    if not is_production(settings):
        print("REFUSE: not production")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        before = await status_counts(pool)
        print("BEFORE", json.dumps(before))
        print("TARGET_STATUSES", ",".join(STATUSES))
        target = sum(int(before.get(s, 0)) for s in STATUSES)
        print("TARGET_COUNT", target)

        if APPLY:
            snapshot = await pool.fetch(
                """
                SELECT id, user_id, batch_id, kind, channel_role, status, error,
                       attempt_count, updated_at
                FROM image_jobs
                WHERE status = ANY($1::text[])
                ORDER BY updated_at ASC
                """,
                STATUSES,
            )
            Path(SNAPSHOT_PATH).write_text(
                json.dumps([dict(r) for r in snapshot], default=str),
                encoding="utf-8",
            )
            print("SNAPSHOT_COUNT", len(snapshot), SNAPSHOT_PATH)

            result = await pool.execute(
                """
                UPDATE image_jobs
                SET status = 'cancelled',
                    updated_at = NOW()
                WHERE status = ANY($1::text[])
                """,
                STATUSES,
            )
            print("CANCELLED", result)
        else:
            print("DRY_RUN: no rows updated")

        after = await status_counts(pool)
        print("AFTER", json.dumps(after))
    finally:
        await pool.close()
    print("CANCEL_IMAGE_JOBS_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def _parse_statuses(argv: list[str]) -> str:
    if "--statuses" in argv:
        idx = argv.index("--statuses")
        if idx + 1 >= len(argv):
            raise SystemExit("--statuses requires a value, e.g. --statuses pending,running")
        return argv[idx + 1]
    return "failed,pending,running"


def main() -> int:
    apply = "--apply" in sys.argv
    statuses = _parse_statuses(sys.argv)
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(
        f"=== cancel image_jobs [{statuses}] "
        f"[{'APPLY' if apply else 'DRY-RUN'}] {host} ==="
    )
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/cancel_image_jobs.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(REMOTE_PY)
            local_py = tmp.name
        sftp = client.open_sftp()
        sftp.put(local_py, remote)
        sftp.close()
        Path(local_py).unlink(missing_ok=True)
        env = f"CX_APPLY={'1' if apply else '0'} CX_STATUSES={statuses}"
        cmd = (
            "set -e\n"
            "chown camxora:camxora " + remote + "\n"
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo PYTHONUNBUFFERED=1 " + env + " "
            "/opt/camxora/repo/platform_api/.venv/bin/python -u " + remote + "'\n"
            "rm -f " + remote + "\n"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-4000:] + "\n")
        if apply:
            local_snap = Path(tempfile.gettempdir()) / "cancelled_image_jobs_snapshot.json"
            try:
                sftp = client.open_sftp()
                sftp.get(
                    "/opt/camxora/tmp/cancelled_image_jobs_snapshot.json",
                    str(local_snap),
                )
                sftp.close()
                print(f"Snapshot saved locally: {local_snap}")
            except Exception as exc:
                print(f"WARNING: could not pull snapshot: {exc}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
