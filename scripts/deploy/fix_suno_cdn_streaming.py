#!/usr/bin/env python3
"""Prod hotfix v8: progressive Suno-CDN streaming when B2 not ready.

_origin_playback_url now returns the stored Suno CDN URL as a 'suno' origin
when no B2 object is ready, so _proxy_row streams it with Range passthrough
(fast start) and the existing branch schedules B2 backfill. Once B2/encryption
is ready the B2 branch takes over automatically. Packaged tracks unchanged.
Backup-first.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL_SERVICE = ROOT / ".dbg" / "prod-webmusic-service" / "web_music_service.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_SERVICE = "/opt/camxora/repo/platform_api/services/web_music_service.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_SERVICE.is_file():
        raise FileNotFoundError(LOCAL_SERVICE)
    print(f"=== hotfix v8 (suno-cdn streaming origin) -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        backup_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            f"cp -p $REPO/services/web_music_service.py $REPO/services/web_music_service.py.pre-sunostream-{STAMP}.bak\n"
            f"ls -la $REPO/services/web_music_service.py.pre-sunostream-{STAMP}.bak\n"
            "echo BACKUP_DONE\n"
        )
        print("-- [1/4] backup --")
        _, sout, serr = client.exec_command(backup_cmd, get_pty=False, timeout=60)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-800:] + "\n")
        if "BACKUP_DONE" not in out:
            return 1

        print("-- [2/4] upload service --")
        sftp = client.open_sftp()
        with sftp.file(REMOTE_SERVICE, "wb") as rf:
            rf.write(LOCAL_SERVICE.read_bytes())
        sftp.close()

        verify_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            "chown camxora:camxora $REPO/services/web_music_service.py\n"
            "echo '=== [3/4] compile + marker ==='\n"
            "$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo SERVICE_OK\n"
            f"grep -n 'No durable B2 object yet: stream progressively' {REMOTE_SERVICE} | head -1\n"
            "echo '=== [4/4] restart + health ==='\n"
            "systemctl restart camxora-api\n"
            "sleep 10\n"
            "systemctl is-active camxora-api || true\n"
            "curl -s -o /dev/null -w 'api_health=%{http_code}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL\n"
            "journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -8 || true\n"
            "echo SUNOSTREAM_DONE\n"
        )
        print("-- [3/4]+[4/4] --")
        _, sout, serr = client.exec_command(verify_cmd, get_pty=False, timeout=200)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "SUNOSTREAM_DONE" not in out or "api_health=200" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
