#!/usr/bin/env python3
"""File-scoped production hotfix: reuse expired web_subscriptions on plan buy.

Uploads local subscription_service.py and restarts camxora-api.
Does not sync a mixed platform_api tree.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
for candidate in (PRIMARY / "scripts" / "deploy", SCRIPT_DIR):
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REPO = SCRIPT_DIR.parents[1]
REL = "platform_api/services/v2/subscription_service.py"


def _run(client, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = out + ("\n" + err if err.strip() else "")
    return code, text.encode("ascii", errors="replace").decode("ascii")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    local = REPO / REL
    if not local.is_file():
        raise SystemExit(f"Missing {local}")
    print(f"Target production host: {host}")
    print(f"Uploading {REL} from local worktree")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote = f"/opt/camxora/repo/{REL}"
        sftp.put(str(local), remote)
        sftp.close()
        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/services/v2/subscription_service.py
grep -n "_REUSABLE_CHECKOUT_STATUSES\|status = 'pending'" \
  $REPO/platform_api/services/v2/subscription_service.py | head -15
systemctl restart camxora-api
health=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  health=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$health
  if [ "$health" = "200" ]; then
    break
  fi
  sleep 2
done
test "$health" = "200"
echo WEB_SUB_EXPIRED_REUSE_PROD_DONE
""",
            timeout=180,
        )
        print(out)
        print(f"exit={code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
