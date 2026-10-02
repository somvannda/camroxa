#!/usr/bin/env python3
"""Verify step for restore v4: chown, py_compile, restart, health, markers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
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

REMOTE_CMD = r"""
set -e
REPO=/opt/camxora/repo/platform_api
chown camxora:camxora $REPO/services/web_music_service.py
echo '=== py_compile ==='
$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo SERVICE_OK
echo '=== markers ==='
echo -n 'canonical_api_path count: '; grep -c 'canonical_api_path' $REPO/services/web_music_service.py || true
echo -n 'http_paths count: '; grep -c 'platform_api.http_paths' $REPO/services/web_music_service.py || true
grep -n "web-music/generations/{task_id}/download" $REPO/services/web_music_service.py | head -1
grep -n 'text-assist LLM failed' $REPO/services/web_music_service.py | head -1
grep -n 'service.generate enter' $REPO/services/web_music_service.py | head -1
echo '=== restart + health ==='
systemctl restart camxora-api
sleep 10
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{http_code}\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -10 || true
echo RESTORE_V4_VERIFY_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0 if "RESTORE_V4_VERIFY_DONE" in out and "api_health=200" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
