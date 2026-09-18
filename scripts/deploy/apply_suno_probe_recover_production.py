#!/usr/bin/env python3
"""Production hotfix #6: health probe self-heals dead URLs from the durable stream host.

Plus a one-time concurrent sweep recovering every currently-unavailable channel.

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
LOCAL_PATCH = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\suno_dl6.patch")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/repositories/batch_repo.py $REPO/platform_api/repositories/batch_repo.py.pre-proberec-$STAMP.bak
cp -p $REPO/platform_api/services/batch_service.py $REPO/platform_api/services/batch_service.py.pre-proberec-$STAMP.bak
echo '=== [2] dry-run ==='
cd $REPO && patch -p1 --binary --dry-run < /tmp/suno_dl6.patch
echo '=== [3] apply ==='
cd $REPO && patch -p1 --binary < /tmp/suno_dl6.patch
echo '=== [4] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile \
  $REPO/platform_api/repositories/batch_repo.py \
  $REPO/platform_api/services/batch_service.py && echo PYCOMPILE_OK
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
echo '=== [6] concurrent recovery sweep ==='
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
    return b[:3] == b"ID3" or (b[0] == 0xFF and (b[1] & 0xE0) == 0xE0)

async def main():
    env = load_env("/opt/camxora/repo/platform_api/.env")
    dsn = env.get("PLATFORM_DATABASE_URL", "")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=2, max_size=8)
    rows = await pool.fetch(
        """
        SELECT id, audio_id_ok, audio_id_alt,
               download_unavailable_ok, download_unavailable_alt
        FROM suno_tasks WHERE status='success'
          AND (COALESCE(download_unavailable_ok,false) OR COALESCE(download_unavailable_alt,false))
        """
    )
    work = []
    for r in rows:
        if r["download_unavailable_ok"] and str(r["audio_id_ok"] or "").strip():
            work.append((r["id"], "ok", str(r["audio_id_ok"]).strip()))
        if r["download_unavailable_alt"] and str(r["audio_id_alt"] or "").strip():
            work.append((r["id"], "alt", str(r["audio_id_alt"]).strip()))
    print("RECOVERY_WORK", len(work))
    sem = asyncio.Semaphore(24)
    hdrs = {"User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)"}
    recovered = failed = 0
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=hdrs) as c:
        async def recover(task_id, ch, aid):
            nonlocal recovered, failed
            async with sem:
                url = f"https://audiostream.api.box/stream/{aid}.mp3"
                try:
                    resp = await c.get(url)
                    if resp.status_code == 200 and is_mp3(resp.content[:16]):
                        await pool.execute(
                            f"""
                            UPDATE suno_tasks
                            SET audio_url_{ch} = $2,
                                download_unavailable_{ch} = false,
                                download_unavailable_at_{ch} = NULL,
                                updated_at = NOW()
                            WHERE id = $1
                            """,
                            task_id,
                            url,
                        )
                        recovered += 1
                        return
                except Exception:
                    pass
                failed += 1
        await asyncio.gather(*(recover(*w) for w in work))
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
echo SUNO_PROBEREC_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_PATCH.is_file():
        raise FileNotFoundError(LOCAL_PATCH)
    print(f"=== hotfix probe-recover -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/suno_dl6.patch", "wb") as remote_file:
            remote_file.write(LOCAL_PATCH.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_PROBEREC_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX6_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
