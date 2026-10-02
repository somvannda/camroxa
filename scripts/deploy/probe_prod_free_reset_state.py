#!/usr/bin/env python3
"""READ-ONLY: verify live prod router file markers + api process + recent journal."""
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

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo/platform_api
echo "--- markers in live router file ---"
grep -c "web-music /generate called" $REPO/routers/web_music.py || echo NO_CALLED_LOG
grep -c "web-music /generate failed" $REPO/routers/web_music.py || echo NO_FAILED_LOG
grep -n "_has_web_subscription(UUID(ctx.user_id))" $REPO/routers/web_music.py || echo NO_NETCAP_PATCH
echo "--- file mtime + process start ---"
ls -la $REPO/routers/web_music.py
systemctl show camxora-api -p ExecMainStartTimestamp -p MainPID 2>/dev/null
echo "--- raw journal tail (last 25 lines, no filter) ---"
journalctl -u camxora-api -n 25 --no-pager 2>/dev/null || true
echo LIVE_FILE_CHECK_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== live file/process check ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
