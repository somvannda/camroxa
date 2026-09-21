#!/usr/bin/env python3
"""Production hotfix #12: web_music WAV backfill in the B2 sweep.

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
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl12.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/repositories/streaming_repo.py $REPO/platform_api/repositories/streaming_repo.py.pre-wav-$STAMP.bak
cp -p $REPO/platform_api/services/streaming_upload_service.py $REPO/platform_api/services/streaming_upload_service.py.pre-wav-$STAMP.bak
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl12.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl12.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/repositories/streaming_repo.py \
  $REPO/platform_api/services/streaming_upload_service.py && echo PYCOMPILE_OK
echo '=== [5] restart + health ==='
systemctl restart camxora-api
for i in 1 2 3 4 5 6; do
  sleep 3
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8100/health || true)
  echo "health_attempt_$i=$code"
  [ "$code" = "200" ] && break
done
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError' | tail -8 || true
echo '=== [6] WAV backfill sweep ==='
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
    row = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE source='web_music' AND COALESCE(b2_wav_storage_key_ok,'')='') AS wav_missing_ok,
          count(*) FILTER (WHERE source='web_music' AND COALESCE(b2_wav_storage_key_alt,'')='') AS wav_missing_alt,
          count(*) FILTER (WHERE source='web_music') AS web_music_total
        FROM suno_tasks WHERE status='success'
        """
    )
    print("WAV_COVERAGE_BEFORE", dict(row))
    from platform_api.services.streaming_upload_service import StreamingUploadService
    svc = StreamingUploadService(pool)
    total = {"wav_backfilled": 0, "wav_failed": 0}
    for i in range(1, 6):
        stats = await svc.run_backfill_sweep(window_hours=336, limit=100, alert=False)
        print(f"  sweep {i}: {stats}")
        total["wav_backfilled"] += stats.get("wav_backfilled", 0)
        total["wav_failed"] += stats.get("wav_failed", 0)
    print("WAV_TOTAL", total)
    row = await pool.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE source='web_music' AND COALESCE(b2_wav_storage_key_ok,'')='') AS wav_missing_ok,
          count(*) FILTER (WHERE source='web_music' AND COALESCE(b2_wav_storage_key_alt,'')='') AS wav_missing_alt
        FROM suno_tasks WHERE status='success'
        """
    )
    print("WAV_COVERAGE_AFTER", dict(row))
    await pool.close()

asyncio.run(main())
PYEOF
echo B2_WAV_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix wav-backfill -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl12.patch", "wb") as rf:
            rf.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=3600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "B2_WAV_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX12_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
