#!/usr/bin/env python3
"""Verify step: chown, py_compile, restart, health check for AI assist hotfix."""
from __future__ import annotations

import sys
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

REMOTE_CMD = r"""
set -e
REPO=/opt/camxora/repo/platform_api
echo "=== [1] chown ==="
chown camxora:camxora $REPO/routers/web_music.py $REPO/services/web_music_service.py
echo "=== [2] py_compile ==="
$REPO/.venv/bin/python -m py_compile $REPO/routers/web_music.py         && echo "ROUTER_COMPILE_OK"
$REPO/.venv/bin/python -m py_compile $REPO/services/web_music_service.py && echo "SERVICE_COMPILE_OK"
echo "=== [3] markers ==="
grep -n "/generate-styles failed" $REPO/routers/web_music.py | head -1
grep -n "/generate-draft failed"  $REPO/routers/web_music.py | head -1
grep -n "text-assist LLM failed"  $REPO/services/web_music_service.py | head -1
grep -n "except ImportError:"     $REPO/services/web_music_service.py | head -1
echo "=== [4] restart + wait ==="
systemctl restart camxora-api
sleep 10
echo "=== [5] health + status ==="
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "2 minutes ago" --no-pager 2>/dev/null | grep -iE "Traceback|Started server process|ModuleNotFoundError|ImportError|ERROR" | tail -12 || true
echo "VERIFY_DONE"
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0 if "VERIFY_DONE" in out and "api_health=200" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
