#!/usr/bin/env python3
"""Production hotfix: surface real errors from AI assist (style + draft) endpoints.

Problem: /generate-styles and /generate-draft called reraise_text_assist_failure()
which ALWAYS returned the generic "AI assist is temporarily unavailable" 502,
hiding the actual DeepSeek/provider error. Also neither endpoint had entry logs
or exception logs, so failures were invisible server-side.

Changes deployed (2 files):
  1. platform_api/routers/web_music.py   - logger.info + logger.exception on BOTH assist endpoints
  2. platform_api/services/web_music_service.py - reraise_text_assist_failure() now
     (a) logger.exception the REAL provider error before wrapping
     (b) forwards the ACTUAL provider error message to the frontend (not always generic)
     + router-level logs identical pattern to /generate.

Backs up both files with timestamped .bak, uploads, py_compile both, restarts
camxora-api, verifies. NO git commit / merge.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL_ROUTER = ROOT / ".dbg" / "prod-webmusic-router" / "web_music.py"
LOCAL_SERVICE = ROOT / ".dbg" / "prod-webmusic-service" / "web_music_service.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_ROUTER = "/opt/camxora/repo/platform_api/routers/web_music.py"
REMOTE_SERVICE = "/opt/camxora/repo/platform_api/services/web_music_service.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
echo "--- backups ---"
cp -p $REPO/routers/web_music.py $REPO/routers/web_music.py.pre-assist-log-$STAMP.bak
cp -p $REPO/services/web_music_service.py $REPO/services/web_music_service.py.pre-assist-err-$STAMP.bak
ls -la $REPO/routers/web_music.py.pre-assist-log-$STAMP.bak $REPO/services/web_music_service.py.pre-assist-err-$STAMP.bak
chown camxora:camxora $REPO/routers/web_music.py $REPO/services/web_music_service.py
echo "--- py_compile ---"
$REPO/.venv/bin/python -m py_compile $REPO/routers/web_music.py
$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py
echo "--- markers ---"
grep -n "/generate-styles failed" $REPO/routers/web_music.py | head -2
grep -n "/generate-draft failed"  $REPO/routers/web_music.py | head -2
grep -n "text-assist LLM failed"  $REPO/services/web_music_service.py | head -2
echo "--- restart api ---"
systemctl restart camxora-api
sleep 6
echo "--- api state ---"
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Started server process" | tail -6 || true
echo FIX_TEXT_ASSIST_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_ROUTER.is_file():
        raise FileNotFoundError(LOCAL_ROUTER)
    if not LOCAL_SERVICE.is_file():
        raise FileNotFoundError(LOCAL_SERVICE)
    print(f"=== Fix AI assist surfacing + logging -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE_ROUTER, "wb") as remote_file:
            remote_file.write(LOCAL_ROUTER.read_bytes())
        print(f"Uploaded router: {LOCAL_ROUTER.as_posix()} -> {REMOTE_ROUTER}")
        with sftp.file(REMOTE_SERVICE, "wb") as remote_file:
            remote_file.write(LOCAL_SERVICE.read_bytes())
        print(f"Uploaded service: {LOCAL_SERVICE.as_posix()} -> {REMOTE_SERVICE}")
        sftp.close()
        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-1500:] + "\n")
        if "FIX_TEXT_ASSIST_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
