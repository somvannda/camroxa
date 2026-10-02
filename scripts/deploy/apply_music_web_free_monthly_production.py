#!/usr/bin/env python3
"""Production-only hotfix: music-web free allowance = monthly (5 songs/month).

Applies the patched files (adapted to prod's older codebase) to 82.197.71.248:
- platform_api/models/products.py            (reset-period keys)
- platform_api/services/billing_calendar.py  (month helpers)
- platform_api/services/v2/credit_service.py (monthly bucket key + copy)

Then data:
- web_music_free_daily_credits  -> 50  (5 songs @ 10 credits/song, per month)
- music_web_free_reset_period   -> monthly

Safety: backs up the three remote files first, py_compiles remotely before SQL,
restores backups on any compile failure, then restarts camxora-api and verifies.

NO git commit / merge is performed. Run only when explicitly asked for production.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "prod-free-reset-hotfix"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_REPO = "/opt/camxora/repo/platform_api"
STAMP = time.strftime("%Y%m%d-%H%M%S")

UPLOADS = [
    (DBG / "models" / "products.py", f"{REMOTE_REPO}/models/products.py"),
    (
        DBG / "services" / "billing_calendar.py",
        f"{REMOTE_REPO}/services/billing_calendar.py",
    ),
    (
        DBG / "services" / "v2" / "credit_service.py",
        f"{REMOTE_REPO}/services/v2/credit_service.py",
    ),
]

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
API=$REPO/platform_api
STAMP="%STAMP%"

echo "--- backup originals ---"
for f in models/products.py services/billing_calendar.py services/v2/credit_service.py; do
  cp -p $API/$f $API/$f.pre-monthly-$STAMP.bak
done
ls -1 $API/models/products.py.pre-monthly-$STAMP.bak \
      $API/services/billing_calendar.py.pre-monthly-$STAMP.bak \
      $API/services/v2/credit_service.py.pre-monthly-$STAMP.bak

echo "--- remote syntax check (fail -> restore) ---"
if ! $API/.venv/bin/python -m py_compile \
      $API/models/products.py \
      $API/services/billing_calendar.py \
      $API/services/v2/credit_service.py; then
  echo "COMPILE FAILED - restoring backups"
  for f in models/products.py services/billing_calendar.py services/v2/credit_service.py; do
    cp -p $API/$f.pre-monthly-$STAMP.bak $API/$f
  done
  exit 2
fi
echo "COMPILE_OK"

echo "--- apply data settings ---"
export $(grep -E '^PLATFORM_DATABASE_URL=' $API/.env | xargs -d '\n')
PYTHONPATH=$REPO $API/.venv/bin/python - <<'PY'
import asyncio, os
import asyncpg

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    upsert = """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE SET value = $2, value_type = $3, updated_at = NOW()
    """
    await pool.execute(upsert, "web_music_free_daily_credits", "50", "int")
    await pool.execute(upsert, "music_web_free_reset_period", "monthly", "string")
    rows = await pool.fetch(
        "SELECT key, value, value_type FROM system_settings WHERE key IN "
        "('web_music_free_daily_credits','music_web_free_reset_period') ORDER BY key"
    )
    for r in rows:
        print(f"setting {r['key']} = {r['value']} ({r['value_type']})")
    await pool.close()

asyncio.run(main())
PY

echo "--- restart api ---"
systemctl restart camxora-api
sleep 5
systemctl is-active camxora-api
curl -sf http://127.0.0.1:8100/health | head -c 300 || echo "HEALTH_FAIL"
echo
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ERROR|UndefinedColumn|ModuleNotFound" | tail -10 || true
echo APPLY_MUSIC_WEB_FREE_MONTHLY_PRODUCTION_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    for local, _remote in UPLOADS:
        if not local.is_file():
            raise FileNotFoundError(local)

    print(f"=== Apply monthly free pool -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, remote in UPLOADS:
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()

        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out + "\n")
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "APPLY_MUSIC_WEB_FREE_MONTHLY_PRODUCTION_DONE" not in out:
            print("Apply did not finish cleanly (see output above).")
            return 1
        print("Apply completed.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
