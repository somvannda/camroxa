#!/usr/bin/env python3
"""ROLLBACK: restore web_music_service.py from the pre-deploy .bak then restart API.
Also: download the ACTUAL prod version of web_music_service.py so we can patch
it locally (not the current main-branch version which has platform_api.http_paths).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DOWNLOAD_SERVICE = ROOT / ".dbg" / "prod-webmusic-service" / "web_music_service.prod.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set -e
REPO=/opt/camxora/repo/platform_api
echo "=== find backup ==="
BAK=$(ls -t $REPO/services/web_music_service.py.pre-assist-err-*.bak 2>/dev/null | head -n 1)
if [ -z "$BAK" ]; then
  echo "NO BACKUP FOUND - aborting rollback path"
  exit 2
fi
echo "Using backup: $BAK"
cp -p "$BAK" $REPO/services/web_music_service.py
chown camxora:camxora $REPO/services/web_music_service.py
$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo "SERVICE_COMPILE_OK"
echo "--- restart ---"
systemctl restart camxora-api
sleep 7
echo "--- health ---"
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 8 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|Started server process|ModuleNotFoundError" | tail -5 || true
echo "ROLLBACK_DONE"
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== Rollback + download prod service file -> {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        if "ROLLBACK_DONE" not in out:
            return 1

        sftp = client.open_sftp()
        DOWNLOAD_SERVICE.parent.mkdir(parents=True, exist_ok=True)
        with sftp.file("/opt/camxora/repo/platform_api/services/web_music_service.py", "rb") as rf:
            data = rf.read()
        DOWNLOAD_SERVICE.write_bytes(data)
        sftp.close()
        print(f"Downloaded actual prod service file to: {DOWNLOAD_SERVICE} ({len(data)} bytes)")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
