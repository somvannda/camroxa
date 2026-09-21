#!/usr/bin/env python3
"""Production hotfix #2: keep web_music out of the desktop download queue.

Web-music tasks are website-only (their B2 object is an encrypted
``application/vnd.camxora.audio`` package, never a plain MP3). The desktop
shell queue was returning them anyway, so every web-music task looped forever.
Also prefer the durable B2/CDN URL for studio channels when archived.

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
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl2.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/repositories/batch_repo.py $REPO/platform_api/repositories/batch_repo.py.pre-wmqueue-$STAMP.bak
cp -p $REPO/platform_api/services/batch_service.py $REPO/platform_api/services/batch_service.py.pre-wmqueue-$STAMP.bak
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl2.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl2.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/repositories/batch_repo.py \
  $REPO/platform_api/services/batch_service.py && echo PYCOMPILE_OK
grep -n "web_music" $REPO/platform_api/repositories/batch_repo.py | head -3
echo '=== [5] restart + health ==='
systemctl restart camxora-api
sleep 12
systemctl is-active camxora-api || true
for i in 1 2 3 4 5 6; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8100/health || echo 000)
  echo "health_attempt_$i=$code"
  [ "$code" = "200" ] && break
  sleep 3
done
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError' | tail -8 || true
echo '=== [6] verify pending by source ==='
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
    rows = await pool.fetch(
        """
        SELECT COALESCE(st.source,'(null)') AS source, count(*) AS n
        FROM suno_tasks st
        WHERE st.status='success'
          AND COALESCE(st.source,'') <> 'web_music'
          AND (
            (COALESCE(st.downloaded_ok,false)=false AND COALESCE(st.download_unavailable_ok,false)=false
             AND (st.audio_url_ok IS NOT NULL OR COALESCE(NULLIF(BTRIM(st.audio_id_ok),''),NULL) IS NOT NULL))
            OR
            (COALESCE(st.downloaded_alt,false)=false AND COALESCE(st.download_unavailable_alt,false)=false
             AND (st.audio_url_alt IS NOT NULL OR COALESCE(NULLIF(BTRIM(st.audio_id_alt),''),NULL) IS NOT NULL))
          )
        GROUP BY 1 ORDER BY n DESC
        """
    )
    print("DESKTOP_PENDING_BY_SOURCE", [dict(r) for r in rows])
    await pool.close()

asyncio.run(main())
PYEOF
echo SUNO_WM_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix web_music-queue -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl2.patch", "wb") as remote_file:
            remote_file.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_WM_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX2_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
