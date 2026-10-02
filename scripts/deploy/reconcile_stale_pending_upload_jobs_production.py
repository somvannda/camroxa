#!/usr/bin/env python3
"""Production: reconcile stale-pending mp3 upload jobs that already have a B2 copy.

A retry can set a job to ``pending`` and then die before flipping it to success,
leaving an archived track stuck as pending in the admin page. These jobs are
already durable in Backblaze, so mark them ``success``.

Scope: kind in (mp3_ok, mp3_alt), status='pending', updated > 10 min ago, and a
non-empty ``stream_tracks.storage_key`` exists for the matching task+variant.

Dry-run by default; pass --apply to write. Refuses non-production hosts.
"""
from __future__ import annotations

import json
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
SNAPSHOT_PATH = "/opt/camxora/tmp/stale_pending_upload_jobs_snapshot.json"

HAS_B2 = """
EXISTS (
  SELECT 1 FROM stream_tracks t
  WHERE t.suno_task_id = j.suno_task_id
    AND t.variant = CASE WHEN j.kind = 'mp3_ok' THEN 'ok' ELSE 'alt' END
    AND COALESCE(t.storage_key, '') <> ''
)
"""
SCOPE = """
j.kind IN ('mp3_ok','mp3_alt')
AND j.status = 'pending'
AND j.updated_at < now() - interval '10 minutes'
AND {has_b2}
""".format(has_b2=HAS_B2)


async def counts(pool) -> dict:
    row = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE j.status='pending' AND j.kind IN ('mp3_ok','mp3_alt')) pending,
          count(*) FILTER (WHERE {scope}) stale_pending_with_b2,
          count(*) FILTER (WHERE j.status='pending' AND j.kind IN ('mp3_ok','mp3_alt') AND NOT {has_b2}) stale_pending_no_b2,
          count(*) FILTER (WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt')) failed,
          count(*) FILTER (WHERE j.status='success' AND j.kind IN ('mp3_ok','mp3_alt')) success
        FROM stream_upload_jobs j
        """.format(scope=SCOPE, has_b2=HAS_B2)
    )
    return dict(row)


async def main() -> int:
    settings = get_settings()
    if not is_production(settings):
        print("REFUSE: not production")
        return 2
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        before = await counts(pool)
        print("BEFORE", json.dumps(before))

        snapshot = await pool.fetch(
            f"""
            SELECT j.id, j.status, j.permanent_failed, j.attempt_count, j.error,
                   j.created_at, j.updated_at
            FROM stream_upload_jobs j
            WHERE {SCOPE}
            """
        )
        Path(SNAPSHOT_PATH).write_text(
            json.dumps([dict(r) for r in snapshot], default=str), encoding="utf-8"
        )
        print("SNAPSHOT_COUNT", len(snapshot), SNAPSHOT_PATH)

        if APPLY:
            result = await pool.execute(
                f"""
                UPDATE stream_upload_jobs j
                SET status = 'success',
                    permanent_failed = false,
                    error = NULL,
                    updated_at = NOW()
                WHERE {SCOPE}
                """
            )
            print("RECONCILED_STALE_PENDING", result)

        after = await counts(pool)
        print("AFTER", json.dumps(after))
    finally:
        await pool.close()
    print("STALE_PENDING_RECONCILE_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
'''


def main() -> int:
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== reconcile stale-pending upload jobs [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/reconcile_stale_pending_upload_jobs.py"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(REMOTE_PY)
            local_py = tmp.name
        sftp = client.open_sftp()
        sftp.put(local_py, remote)
        sftp.close()
        Path(local_py).unlink(missing_ok=True)
        env = f"CX_APPLY={'1' if apply else '0'}"
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
            sys.stderr.write(err[-3000:] + "\n")
        if apply:
            local_snap = Path(tempfile.gettempdir()) / "stale_pending_upload_jobs_snapshot.json"
            try:
                sftp = client.open_sftp()
                sftp.get("/opt/camxora/tmp/stale_pending_upload_jobs_snapshot.json", str(local_snap))
                sftp.close()
                print(f"Snapshot saved locally: {local_snap}")
            except Exception as exc:
                print(f"WARNING: could not pull snapshot: {exc}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
