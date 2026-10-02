#!/usr/bin/env python3
"""Prod hotfix v4: RESTORE prod-era web_music_service.py + re-apply approved patches.

Why: hotfix v1/v2 (17:12-17:19) accidentally uploaded a MAIN-branch-era
web_music_service.py onto prod's OLDER v1-only tree. Main-era builds media URLs
via canonical_api_path -> /api/v3/... which 404 on prod (v1-only backend). This
restores the prod-era service (v1 URLs, submit_suno flow, monthly quota) and
re-applies ONLY the approved changes:
  - reraise_text_assist_failure(): log real provider error + forward its message
  - service.generate(): entry + step logs for failure tracing
Router (web_music.py) is prod-era already and unchanged this deploy.
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
    print(f"=== restore prod-era service + patches -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        backup_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            f"cp -p $REPO/services/web_music_service.py $REPO/services/web_music_service.py.pre-restore-{STAMP}.bak\n"
            f"ls -la $REPO/services/web_music_service.py.pre-restore-{STAMP}.bak\n"
            "echo BACKUP_DONE\n"
        )
        print("-- [1/4] backup current (main-era) running service --")
        _, sout, serr = client.exec_command(backup_cmd, get_pty=False, timeout=60)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-800:] + "\n")
        if "BACKUP_DONE" not in out:
            return 1

        print("-- [2/4] upload restored prod-era service --")
        sftp = client.open_sftp()
        with sftp.file(REMOTE_SERVICE, "wb") as rf:
            rf.write(LOCAL_SERVICE.read_bytes())
        sftp.close()
        print(f"  uploaded {LOCAL_SERVICE.name} ({LOCAL_SERVICE.stat().st_size} B)")

        verify_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            "chown camxora:camxora $REPO/services/web_music_service.py\n"
            "echo '=== [3/4] py_compile ==='\n"
            "$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo SERVICE_OK\n"
            "echo '=== markers (expect v1 URLs + reraise log + NO canonical_api_path/http_paths) ==='\n"
            f"grep -c 'canonical_api_path' {REMOTE_SERVICE} || echo '0 canonical (GOOD)'\n"
            f"grep -c 'platform_api.http_paths' {REMOTE_SERVICE} || echo '0 http_paths (GOOD)'\n"
            f"grep -n '/api/v1/web-music/generations/{task_id}/download' {REMOTE_SERVICE} | head -1\n"
            f"grep -n 'text-assist LLM failed' {REMOTE_SERVICE} | head -1\n"
            f"grep -n 'service.generate enter' {REMOTE_SERVICE} | head -1\n"
            "echo '=== [4/4] restart + health ==='\n"
            "systemctl restart camxora-api\n"
            "sleep 10\n"
            "systemctl is-active camxora-api || true\n"
            "curl -s -o /dev/null -w 'api_health=%{http_code}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL\n"
            "journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -10 || true\n"
            "echo RESTORE_V4_DONE\n"
        )
        print("-- [3/4]+[4/4] compile + restart + health --")
        _, sout, serr = client.exec_command(verify_cmd, get_pty=False, timeout=200)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "RESTORE_V4_DONE" not in out or "api_health=200" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
