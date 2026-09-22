#!/usr/bin/env python3
"""Production hotfix #5 + recovery.

1. Prefer the durable ``audiostream.api.box`` host over the short-lived
   ``tempfile.aiquickdraw.com`` link when the provider returns both.
2. Keep the Progress row incomplete (pipeline waits) when a channel is terminal.
3. Recover every channel marked unavailable by pointing it at the durable host
   (verified MP3) and clearing the terminal flag, so the desktop can download it.

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
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl5.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/clients/suno_client.py $REPO/platform_api/clients/suno_client.py.pre-streamhost-$STAMP.bak
cp -p $REPO/platform_api/routers/progress.py $REPO/platform_api/routers/progress.py.pre-wait-$STAMP.bak
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl5.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl5.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/platform_api/routers/progress.py && echo PYCOMPILE_OK
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
echo '=== [6] recover unavailable channels via durable host ==='
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo $REPO/platform_api/.venv/bin/python - <<'PYEOF'
import asyncio
from pathlib import Path
import asyncpg
import httpx

def load_env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

def is_mp3(b):
    if len(b) < 12:
        return False
    if b[:3] == b"ID3":
        return True
    if b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
        return True
    return False

async def main():
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    rows = await pool.fetch(
        """
        SELECT id, audio_id_ok, audio_id_alt,
               download_unavailable_ok, download_unavailable_alt
        FROM suno_tasks
        WHERE status='success'
          AND (COALESCE(download_unavailable_ok,false) OR COALESCE(download_unavailable_alt,false))
        """
    )
    hdrs = {"User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)"}
    recovered = failed = 0
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=hdrs) as c:
        for r in rows:
            for ch, aid, unavail in (
                ("ok", r["audio_id_ok"], r["download_unavailable_ok"]),
                ("alt", r["audio_id_alt"], r["download_unavailable_alt"]),
            ):
                if not unavail:
                    continue
                aid = str(aid or "").strip()
                if not aid:
                    failed += 1
                    print("  NO_AUDIO_ID", str(r["id"])[:8], ch)
                    continue
                url = f"https://audiostream.api.box/stream/{aid}.mp3"
                try:
                    resp = await c.get(url)
                    body = resp.content
                except Exception as exc:
                    failed += 1
                    print("  ERR", str(r["id"])[:8], ch, type(exc).__name__)
                    continue
                if resp.status_code != 200 or not is_mp3(body[:16]):
                    failed += 1
                    print("  NOT_RECOVERABLE", str(r["id"])[:8], ch, resp.status_code, len(body))
                    continue
                await pool.execute(
                    f"""
                    UPDATE suno_tasks
                    SET audio_url_{ch} = $2,
                        download_unavailable_{ch} = false,
                        download_unavailable_at_{ch} = NULL,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    r["id"],
                    url,
                )
                recovered += 1
    print(f"RECOVERED={recovered} FAILED={failed}")
    left = await pool.fetchval(
        """
        SELECT count(*) FROM suno_tasks WHERE status='success'
          AND (COALESCE(download_unavailable_ok,false) OR COALESCE(download_unavailable_alt,false))
        """
    )
    print("UNAVAILABLE_CHANNELS_REMAINING", int(left))
    await pool.close()

asyncio.run(main())
PYEOF
echo SUNO_STREAMHOST_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix stream-host + recover -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl5.patch", "wb") as remote_file:
            remote_file.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_STREAMHOST_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX5_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
