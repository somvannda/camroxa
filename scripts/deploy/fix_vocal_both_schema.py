#!/usr/bin/env python3
"""Prod hotfix v6: allow vocal_gender 'both' in /generate schema.

Frontend create page sends vocal_gender 'm'|'f'|'both'; backend Literal was
m/f/"" only, so selecting "Both" produced 422. Service already maps 'both' ->
no constraint. Backup-first deploy.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL_ROUTER = ROOT / ".dbg" / "prod-webmusic-router" / "web_music.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_ROUTER = "/opt/camxora/repo/platform_api/routers/web_music.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL_ROUTER.is_file():
        raise FileNotFoundError(LOCAL_ROUTER)
    print(f"=== hotfix v6 (vocal 'both' schema) -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        backup_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            f"cp -p $REPO/routers/web_music.py $REPO/routers/web_music.py.pre-vocalboth-{STAMP}.bak\n"
            f"ls -la $REPO/routers/web_music.py.pre-vocalboth-{STAMP}.bak\n"
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

        print("-- [2/4] upload router --")
        sftp = client.open_sftp()
        with sftp.file(REMOTE_ROUTER, "wb") as rf:
            rf.write(LOCAL_ROUTER.read_bytes())
        sftp.close()

        verify_cmd = (
            "set -e\n"
            "REPO=/opt/camxora/repo/platform_api\n"
            "chown camxora:camxora $REPO/routers/web_music.py\n"
            "echo '=== [3/4] compile + marker ==='\n"
            "$REPO/.venv/bin/python -m py_compile $REPO/routers/web_music.py && echo ROUTER_OK\n"
            f"grep -n 'vocal_gender: Literal' {REMOTE_ROUTER}\n"
            "echo '=== [4/4] restart + health ==='\n"
            "systemctl restart camxora-api\n"
            "sleep 10\n"
            "systemctl is-active camxora-api || true\n"
            "curl -s -o /dev/null -w 'api_health=%{http_code}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL\n"
            "journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -8 || true\n"
            "echo HOTFIX_VOCAL_DONE\n"
        )
        print("-- [3/4]+[4/4] --")
        _, sout, serr = client.exec_command(verify_cmd, get_pty=False, timeout=200)
        out = sout.read().decode("utf-8", errors="replace")
        err = serr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "HOTFIX_VOCAL_DONE" not in out or "api_health=200" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
