#!/usr/bin/env python3
"""Production: upload Telegram ops notifier (includes login alerts) and restart API."""

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
REL = "platform_api/services/telegram_ops_alert_service.py"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    local = ROOT / REL
    if not local.is_file():
        raise FileNotFoundError(local)
    print(f"=== Telegram login alerts -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote = f"/opt/camxora/repo/{REL}"
        with sftp.file(remote, "wb") as rf:
            rf.write(local.read_bytes())
        sftp.close()
        print(f"Uploaded {REL}")
        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/platform_api/services/telegram_ops_alert_service.py
python3 -m py_compile $REPO/platform_api/services/telegram_ops_alert_service.py
grep -n "_patch_login\|notify_login\|LOGIN" $REPO/platform_api/services/telegram_ops_alert_service.py | head
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -sS -m 3 -o /tmp/prod_tg_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then
    echo HEALTH_OK
    break
  fi
  sleep 2
done
test "$code" = "200"
journalctl -u camxora-api -n 40 --no-pager | grep -i 'Telegram ops hooks installed on user login' | tail -5
echo TELEGRAM_LOGIN_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err[-1500:].encode("ascii", "replace").decode("ascii"))
        if "TELEGRAM_LOGIN_PRODUCTION_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
