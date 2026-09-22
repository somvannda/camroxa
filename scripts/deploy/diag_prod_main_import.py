#!/usr/bin/env python3
"""READ-ONLY: diagnose prod platform_api.main import failure (env vs systemd)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

CMD = r'''
REPO=/opt/camxora/repo
API=$REPO/platform_api
echo "=== unit env ==="
systemctl cat camxora-api | grep -iE '^Environment|^WorkingDirectory|^ExecStart' || true
echo "=== import streaming modules ==="
sudo -u camxora env PYTHONPATH=$REPO $API/.venv/bin/python -c "import platform_api.services.streaming_upload_service; print('SVC_OK')" 2>&1 | tail -5
echo "=== import main (stderr captured) ==="
sudo -u camxora bash -lc "cd $REPO/platform_api && PYTHONPATH=$REPO .venv/bin/python -c 'import platform_api.main; print(\"MAIN_OK\")'" 2>&1 | tail -30
echo "=== import main from repo root ==="
sudo -u camxora bash -lc "cd $REPO && PYTHONPATH=$REPO platform_api/.venv/bin/python -c 'import platform_api.main; print(\"MAIN_OK2\")'" 2>&1 | tail -15
echo DIAG_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== main import diagnosis on {host} ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=240)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:])
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
