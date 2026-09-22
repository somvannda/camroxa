#!/usr/bin/env python3
"""Production hotfix: accept fractional wallet_balance in preflight/quota.

File-scoped: uploads only platform_api/models/schemas.py (verified to differ
from prod by exactly the two wallet_balance int -> float lines), backs up,
py_compiles, restarts camxora-api, and verifies. NO git merge / full sync.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / "platform_api" / "models" / "schemas.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/opt/camxora/repo/platform_api/models/schemas.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
cp -p $REPO/models/schemas.py $REPO/models/schemas.py.pre-wallet-float-$STAMP.bak
chown camxora:camxora $REPO/models/schemas.py
$REPO/.venv/bin/python -m py_compile $REPO/models/schemas.py
echo "--- wallet_balance lines ---"
grep -n 'wallet_balance' $REPO/models/schemas.py
systemctl restart camxora-api
sleep 6
echo "--- api state ---"
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL
echo "--- log tail ---"
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Application startup|Uvicorn running|Started server" | tail -8 || true
echo FIX_WALLET_FLOAT_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL.is_file():
        raise FileNotFoundError(LOCAL)
    print(f"=== File-scoped hotfix: schemas.py -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE, "wb") as remote_file:
            remote_file.write(LOCAL.read_bytes())
        sftp.close()
        print(f"Uploaded {LOCAL.as_posix()} -> {REMOTE}")
        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-1500:] + "\n")
        if "FIX_WALLET_FLOAT_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
