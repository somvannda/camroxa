#!/usr/bin/env python3
"""Production hotfix: emit whole-number wallet_balance on /batches/preflight.

Backward compatibility for desktop clients <= 1.3.2, whose
MusicPlanPreflightResponse.wallet_balance is typed int and rejects fractional
display credits. File-scoped: uploads only platform_api/routers/batch.py
(verified to differ from prod by exactly the rounding line), backs up,
py_compiles, restarts camxora-api, and verifies. NO git merge / full sync.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / "platform_api" / "routers" / "batch.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/opt/camxora/repo/platform_api/routers/batch.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
cp -p $REPO/routers/batch.py $REPO/routers/batch.py.pre-wallet-compat-$STAMP.bak
chown camxora:camxora $REPO/routers/batch.py
$REPO/.venv/bin/python -m py_compile $REPO/routers/batch.py
grep -n 'wallet_balance' $REPO/routers/batch.py
systemctl restart camxora-api
sleep 6
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Started server" | tail -5 || true
echo FIX_WALLET_COMPAT_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL.is_file():
        raise FileNotFoundError(LOCAL)
    print(f"=== File-scoped hotfix: routers/batch.py -> production ({host}) ===")
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
        if "FIX_WALLET_COMPAT_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
