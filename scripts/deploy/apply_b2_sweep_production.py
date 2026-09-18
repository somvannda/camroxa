#!/usr/bin/env python3
"""Production hotfix #11: durable B2 backfill sweep + permanent-fail + final retry.

Host must be 82.197.71.248.
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
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl11.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
for f in repositories/streaming_repo.py services/streaming_upload_service.py routers/streaming_admin.py main.py; do
  cp -p $REPO/platform_api/$f $REPO/platform_api/$f.pre-b2sweep-$STAMP.bak
done
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl11.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl11.patch
echo '=== [4] DDL (idempotent) ==='
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
        ALTER TABLE stream_upload_jobs
        ADD COLUMN IF NOT EXISTS permanent_failed BOOLEAN NOT NULL DEFAULT false,
        ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ
        """
    )
    await pool.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_stream_upload_jobs_backfill
        ON stream_upload_jobs (status, permanent_failed, created_at)
        """
    )
    print("DDL_OK")
    await pool.close()

asyncio.run(main())
PYEOF
echo '=== [5] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/repositories/streaming_repo.py \
  $REPO/platform_api/services/streaming_upload_service.py \
  $REPO/platform_api/routers/streaming_admin.py \
  $REPO/platform_api/main.py && echo PYCOMPILE_OK
echo '=== [6] restart + health ==='
systemctl restart camxora-api
for i in 1 2 3 4 5 6; do
  sleep 3
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8100/health || true)
  echo "health_attempt_$i=$code"
  [ "$code" = "200" ] && break
done
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError|B2 backfill' | tail -10 || true
echo '=== [7] final retry + permanent-fail + first sweep ==='
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo $REPO/platform_api/.venv/bin/python - <<'PYEOF'
import asyncio, os
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
    for k, v in env.items():
        os.environ.setdefault(k, v)
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=6)
    from platform_api.services.streaming_upload_service import StreamingUploadService
    svc = StreamingUploadService(pool)

    # 1) Final retry for jobs within the last 14 days (recovery window).
    total_retried = total_ok = total_failed = 0
    for i in range(1, 7):
        result = await svc.retry_failed_jobs(limit=120, max_age_hours=336)
        print(f"  retry pass {i}: {result}")
        total_retried += int(result.get("retried", 0))
        total_ok += int(result.get("succeeded", 0))
        total_failed += int(result.get("failed", 0))
        if int(result.get("retried", 0)) == 0:
            break
    print(f"FINAL_RETRY retried={total_retried} ok={total_ok} failed={total_failed}")

    # 2) Mark every remaining failed job as permanently failed (no more retries).
    marked = await pool.execute(
        """
        UPDATE stream_upload_jobs
        SET permanent_failed = true, updated_at = NOW()
        WHERE status = 'failed' AND COALESCE(permanent_failed, false) = false
        """
    )
    print("PERMANENT_MARKED", marked)
    left = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE status='failed' AND NOT permanent_failed) AS retryable_failed,
          count(*) FILTER (WHERE permanent_failed) AS permanent,
          count(*) FILTER (WHERE status='pending') AS pending
        FROM stream_upload_jobs
        """
    )
    print("JOB_STATE", dict(left))

    # 3) One durable backfill sweep pass.
    stats = await svc.run_backfill_sweep(window_hours=336, limit=200)
    print("BACKFILL_SWEEP", stats)
    await pool.close()

asyncio.run(main())
PYEOF
echo B2_SWEEP_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix b2-sweep -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl11.patch", "wb") as rf:
            rf.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=7200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "B2_SWEEP_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX11_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
