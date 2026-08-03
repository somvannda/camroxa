#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    cmd = r"""
set -e
sleep 8
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'HEALTH_LOCAL_%{http_code}\n' --max-time 10 http://127.0.0.1:8000/health || true
curl -s -o /dev/null -w 'HEALTH_API_%{http_code}\n' --max-time 10 https://api.camxora.com/health || true
cd /opt/camxora/repo
/opt/camxora/venv/bin/python -c 'from platform_api.services.provider_key_balance_service import ProviderKeyBalanceService; print("IMPORT_OK")' 2>&1 | tail -8
journalctl -u camxora-api -n 40 --no-pager | tail -50
echo CHECK_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
