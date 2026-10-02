#!/usr/bin/env python3
"""Production: mark failed mp3 upload jobs whose track is already in B2 as success.

Only touches jobs with status='failed' AND kind in (mp3_ok, mp3_alt) whose
task+variant already has a non-empty stream_tracks.storage_key. Leaves genuinely
missing (no-B2) failures untouched. Dry-run by default; pass --apply.
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
HAS_B2 = """
EXISTS (
  SELECT 1 FROM stream_tracks t
  WHERE t.suno_task_id = j.suno_task_id
    AND t.variant = CASE WHEN j.kind='mp3_ok' THEN 'ok' ELSE 'alt' END
    AND COALESCE(t.storage_key,'') <> ''
)
"""


async def counts(pool):
    row = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt')) failed,
          count(*) FILTER (WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') AND {has_b2}) failed_with_b2,
          count(*) FILTER (WHERE j.status='failed' AND j.kind IN ('mp3_ok','mp3_alt') AND NOT {has_b2}) failed_no_b2
        FROM stream_upload_jobs j
        """.format(has_b2=HAS_B2)
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
        print("BEFORE", json.dumps(await counts(pool)))
        if APPLY:
            result = await pool.execute(
                """
                UPDATE stream_upload_jobs j
                SET status = 'success',
                    permanent_failed = false,
                    error = NULL,
                    updated_at = NOW()
                WHERE j.status = 'failed'
                  AND j.kind IN ('mp3_ok','mp3_alt')
                  AND {has_b2}
                """.format(has_b2=HAS_B2)
            )
            print("RECONCILED", result)
        print("AFTER", json.dumps(await counts(pool)))
    finally:
        await pool.close()
    print("FAILED_RECONCILE_DONE")
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
    print(f"=== reconcile failed jobs with B2 [{'APPLY' if apply else 'DRY-RUN'}] {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        remote = "/opt/camxora/tmp/reconcile_failed_jobs_with_b2.py"
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
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
