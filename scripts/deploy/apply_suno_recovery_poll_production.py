#!/usr/bin/env python3
"""Production hotfix #10: recovery resolver polls async results + fleet sweep.

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
LOCAL_FN = Path(r"C:\Users\KONGSO~1\AppData\Local\Temp\opencode\recover_fn.txt")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP=''' + STAMP + r'''
echo '=== [1] backup ==='
cp -p $REPO/platform_api/services/suno_audio_resolver.py $REPO/platform_api/services/suno_audio_resolver.py.pre-recpoll-$STAMP.bak
echo '=== [2] replace resolver function ==='
$REPO/platform_api/.venv/bin/python - <<'PYEOF'
from pathlib import Path
p = Path("/opt/camxora/repo/platform_api/services/suno_audio_resolver.py")
text = p.read_text(encoding="utf-8")
fn = Path("/tmp/recover_fn.txt").read_text(encoding="utf-8").strip("\n")
marker = "async def recover_suno_task_download_urls"
idx = text.find(marker)
if idx == -1:
    text = text.rstrip("\n") + "\n\n" + fn + "\n"
    print("RESOLVER_APPENDED")
else:
    text = text[:idx].rstrip("\n") + "\n\n" + fn + "\n"
    print("RESOLVER_REPLACED")
p.write_text(text, encoding="utf-8")
PYEOF
echo '=== [3] compile ==='
$REPO/platform_api/.venv/bin/python -m py_compile $REPO/platform_api/services/suno_audio_resolver.py && echo PYCOMPILE_OK
echo '=== [4] restart + health ==='
systemctl restart camxora-api
for i in 1 2 3 4 5 6; do
  sleep 3
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8100/health || true)
  echo "health_attempt_$i=$code"
  [ "$code" = "200" ] && break
done
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null \
  | grep -iE 'Traceback|ImportError|ModuleNotFoundError' | tail -8 || true
echo '=== [5] fleet recovery sweep (with polling) ==='
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
    from platform_api.services.suno_audio_resolver import recover_suno_task_download_urls

    rows = await pool.fetch(
        """
        SELECT id, external_task_id, title, audio_id_ok, audio_id_alt,
               download_unavailable_ok, download_unavailable_alt
        FROM suno_tasks
        WHERE status='success'
          AND (COALESCE(download_unavailable_ok,false) OR COALESCE(download_unavailable_alt,false))
        ORDER BY created_at DESC
        """
    )
    print("SWEEP_TASKS", len(rows))
    recovered = failed = 0
    for r in rows:
        ext = str(r["external_task_id"] or "").strip()
        if not ext:
            failed += 1
            continue
        try:
            mapping = await recover_suno_task_download_urls(pool, ext)
        except Exception as exc:
            print("  recover ERR", str(r["id"])[:8], type(exc).__name__, str(exc)[:80])
            failed += 1
            continue
        did = False
        for ch, aid, unavail in (
            ("ok", r["audio_id_ok"], r["download_unavailable_ok"]),
            ("alt", r["audio_id_alt"], r["download_unavailable_alt"]),
        ):
            if not unavail:
                continue
            url = mapping.get(str(aid or "").strip())
            if not url:
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
            did = True
        if did:
            recovered += 1
            print("  RECOVERED", str(r["id"])[:8], r["title"])
        else:
            failed += 1
        await asyncio.sleep(0.5)
    print(f"SWEEP_RECOVERED_TASKS={recovered} NOT_RECOVERED={failed}")
    left = await pool.fetchval(
        """
        SELECT count(*) FROM suno_tasks WHERE status='success'
          AND (COALESCE(download_unavailable_ok,false) OR COALESCE(download_unavailable_alt,false))
        """
    )
    print("UNAVAILABLE_CHANNELS_REMAINING_TASKS", int(left))
    await pool.close()

asyncio.run(main())
PYEOF
echo SUNO_RECOVERY_POLL_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_FN.is_file():
        raise FileNotFoundError(LOCAL_FN)
    print(f"=== hotfix recovery-poll -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/recover_fn.txt", "wb") as rf:
            rf.write(LOCAL_FN.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=2400)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-3000:] + "\n")
        if "SUNO_RECOVERY_POLL_DONE" not in out or "PYCOMPILE_OK" not in out:
            print("HOTFIX10_INCOMPLETE")
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
