#!/usr/bin/env python3
"""Bump web-music asset recovery per-pass budgets on prod via .env knobs."""
from __future__ import annotations

import sys
import time
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
STAMP = time.strftime("%Y%m%d-%H%M%S")
ENV = "/opt/camxora/repo/platform_api/.env"

REMOTE_CMD = f"""
set -e
echo '=== [1] backup .env ==='
cp -p {ENV} {ENV}.pre-wavbudget-{STAMP}.bak
ls -la {ENV}.pre-wavbudget-{STAMP}.bak
echo '=== [2] append knobs (idempotent) ==='
touch {ENV}
grep -q '^WEB_MUSIC_ASSET_WAV_MAX_PER_PASS=' {ENV} || echo 'WEB_MUSIC_ASSET_WAV_MAX_PER_PASS=6' >> {ENV}
grep -q '^WEB_MUSIC_ASSET_PASS_TASK_LIMIT=' {ENV} || echo 'WEB_MUSIC_ASSET_PASS_TASK_LIMIT=16' >> {ENV}
grep -nE '^WEB_MUSIC_ASSET_(WAV_MAX_PER_PASS|PASS_TASK_LIMIT)=' {ENV}
echo '=== [3] restart + health ==='
systemctl restart camxora-api
sleep 10
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError' | tail -5 || true
echo WAV_BUDGET_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== bump wav recovery budget -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "WAV_BUDGET_DONE" not in out or "api_health=200" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
