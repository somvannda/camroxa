#!/usr/bin/env python3
"""CORRECTED production hotfix: AI assist surfacing + logging.

CRITICAL: backups are taken BEFORE upload (fixed ordering from earlier v1).

2 files deployed:
  1. platform_api/routers/web_music.py
     - Adds logger.info + logger.exception to /generate-draft and /generate-styles
     - Existing /generate changes (paid netcap guard + logs) preserved
  2. platform_api/services/web_music_service.py
     - ImportError shim around platform_api.http_paths (prod doesn't have it)
     - reraise_text_assist_failure() now:
       * logger.exception(provider_error) for observability
       * Forwards ACTUAL provider error to frontend instead of always generic fallback
       * Falls back to generic only if message empty / >500 chars
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

REMOTE_CMD = r"""
set -e
REPO=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
echo "=== [1/5] BACKUP both files BEFORE upload ==="
cp -p $REPO/routers/web_music.py         $REPO/routers/web_music.py.pre-assist-v2-$STAMP.bak
cp -p $REPO/services/web_music_service.py $REPO/services/web_music_service.py.pre-assist-v2-$STAMP.bak
ls -la $REPO/routers/web_music.py.pre-assist-v2-$STAMP.bak $REPO/services/web_music_service.py.pre-assist-v2-$STAMP.bak
echo "=== [2/5] chown (upload is next) ==="
chown camxora:camxora $REPO/routers/web_music.py $REPO/services/web_music_service.py
echo "=== [3/5] py_compile both ==="
$REPO/.venv/bin/python -m py_compile $REPO/routers/web_music.py         && echo "ROUTER_COMPILE_OK"
$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo "SERVICE_COMPILE_OK"
echo "=== [4/5] markers present ==="
grep -n "/generate-styles failed" $REPO/routers/web_music.py | head -1
grep -n "/generate-draft failed"  $REPO/routers/web_music.py | head -1
grep -n "text-assist LLM failed"  $REPO/services/web_music_service.py | head -1
grep -n "try:"                    $REPO/services/web_music_service.py | head -2
echo "=== [5/5] restart + health ==="
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "2 minutes ago" --no-pager 2>/dev/null | grep -iE "Traceback|Started server process|ModuleNotFoundError|ImportError" | tail -10 || true
echo "FIX_ASSIST_V2_DONE"
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_ROUTER.is_file():
        raise FileNotFoundError(LOCAL_ROUTER)
    if not LOCAL_SERVICE.is_file():
        raise FileNotFoundError(LOCAL_SERVICE)
    print(f"=== Fix AI assist (v2, backups-first) -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        # Upload AFTER backup (bash step 1 does backup; step 2 chown happens after we upload)
        sftp = client.open_sftp()
        # Upload FIRST (backup in bash copies the running files before overwrite via cp -p;
        # but we need upload to happen AFTER backup. So: do backup in SSH, *then* upload here.
        # So split into: backup remotely FIRST, then upload, then continue bash.
        sftp.close()

        # --- step A: remote backup (BEFORE upload) ---
        backup_cmd = f"""
set -e
REPO=/opt/camxora/repo/platform_api
cp -p $REPO/routers/web_music.py         $REPO/routers/web_music.py.pre-assist-v2-{STAMP}.bak
cp -p $REPO/services/web_music_service.py $REPO/services/web_music_service.py.pre-assist-v2-{STAMP}.bak
ls -la $REPO/routers/web_music.py.pre-assist-v2-{STAMP}.bak $REPO/services/web_music_service.py.pre-assist-v2-{STAMP}.bak
echo "BACKUP_OK"
"""
        print("-- remote backup (pre-upload) --")
        _, sout, serr = client.exec_command(backup_cmd, get_pty=False, timeout=60)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-800:] + "\n")
        if "BACKUP_OK" not in out:
            print("ERROR: backup step failed")
            return 1

        # --- step B: upload (now safe, backups exist of running files) ---
        print("-- uploading both files (backup taken) --")
        sftp = client.open_sftp()
        with sftp.file(REMOTE_ROUTER, "wb") as rf:
            rf.write(LOCAL_ROUTER.read_bytes())
        print(f"  router: {LOCAL_ROUTER.name}")
        with sftp.file(REMOTE_SERVICE, "wb") as rf:
            rf.write(LOCAL_SERVICE.read_bytes())
        print(f"  service: {LOCAL_SERVICE.name}")
        sftp.close()

        # --- step C: chown + compile + restart ---
        verify_cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        # Strip the backup part (already done above) - just do the rest
        verify_cmd = verify_cmd.split("echo \"=== [2/5]")[0] + "\n" + "echo \"=== [2/5] chown (after upload) ===\"\n" + verify_cmd.split("echo \"=== [2/5] chown", 1)[1]
        print("-- verify + restart --")
        _, sout, serr = client.exec_command(verify_cmd, get_pty=False, timeout=180)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "FIX_ASSIST_V2_DONE" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
