#!/usr/bin/env python3
"""Production hotfix: stop the desktop retrying permanently-dead Suno MP3 URLs.

Applies a minimal patch (prod base) to:
  * platform_api/repositories/batch_repo.py  — exclude terminal channels from
    the pending-download query + add health-probe helpers.
  * platform_api/services/batch_service.py   — debounced dead-URL probe on each
    pending poll; mark gone channels terminal; back up any still-alive ones.

Adds the ``download_unavailable_ok/alt`` columns directly (prod alembic head is
115 while main is 119, so the repo migration is only for main's lineage), then
runs a one-time fleet-wide sweep to unstick existing clients.

Host must be 82.197.71.248. Read-only until the patch/DDL steps.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl.patch")
REMOTE_PATCH = "/tmp/suno_dl.patch"

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/repositories/batch_repo.py $REPO/platform_api/repositories/batch_repo.py.pre-sunodead-$STAMP.bak
cp -p $REPO/platform_api/services/batch_service.py $REPO/platform_api/services/batch_service.py.pre-sunodead-$STAMP.bak
ls -la $REPO/platform_api/repositories/batch_repo.py.pre-sunodead-$STAMP.bak

echo '=== [2] patch dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl.patch
echo '=== [3] patch apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/repositories/batch_repo.py \
  $REPO/platform_api/services/batch_service.py && echo PYCOMPILE_OK
grep -n "download_unavailable_ok" $REPO/platform_api/repositories/batch_repo.py | head -3

echo '=== [5] DDL (idempotent) ==='
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo $REPO/platform_api/.venv/bin/python - <<'PYEOF'
import asyncio
from pathlib import Path
import asyncpg

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

async def main():
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    await pool.execute(
        """
        ALTER TABLE suno_tasks
        ADD COLUMN IF NOT EXISTS download_unavailable_ok BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS download_unavailable_alt BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS download_unavailable_at_ok TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS download_unavailable_at_alt TIMESTAMPTZ
        """
    )
    cols = await pool.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='suno_tasks' AND column_name LIKE 'download_unavailable%'"
    )
    print("DDL_COLS", sorted(c["column_name"] for c in cols))
    await pool.close()

asyncio.run(main())
PYEOF

echo '=== [6] restart + health ==='
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{http_code}\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError|Started server process' | tail -8 || true

echo '=== [7] one-time fleet sweep ==='
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo $REPO/platform_api/.venv/bin/python - <<'PYEOF'
import asyncio
from pathlib import Path
import asyncpg

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

async def main():
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)

    from platform_api.dependencies import set_db_pool
    set_db_pool(pool)
    from platform_api.repositories.batch_repo import BatchRepository
    from platform_api.services.batch_service import BatchService

    repo = BatchRepository(pool)
    svc = BatchService(
        batch_repo=repo,
        credit_service=None,
        pricing_service=None,
        generation_service=None,
        profile_repo=None,
        ai_routing_service=None,
    )
    rows = await pool.fetch(
        """
        SELECT DISTINCT user_id FROM suno_tasks
        WHERE status='success'
          AND (NOT COALESCE(downloaded_ok,false) OR NOT COALESCE(downloaded_alt,false))
        """
    )
    print("USERS_WITH_PENDING", len(rows))
    total = 0
    for r in rows:
        uid = str(r["user_id"])
        for _ in range(8):
            try:
                marked = await svc.probe_dead_suno_downloads(user_id=uid, limit=25)
            except Exception as exc:
                print("probe failed", uid, type(exc).__name__, str(exc)[:140])
                break
            total += marked
            if marked == 0:
                break
    print("SWEEP_MARKED_TOTAL", total)
    await pool.close()

asyncio.run(main())
PYEOF
echo SUNO_DL_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix suno-dead-downloads -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE_PATCH, "wb") as remote_file:
            remote_file.write(LOCAL_PATCH.read_bytes())
        sftp.close()

        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_DL_DONE" not in out or "api_health=200" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
