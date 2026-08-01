#!/usr/bin/env python3
"""Run alembic upgrade head on production and print migration status."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

REMOTE = r"""
set -e
REPO=/opt/camxora/repo
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
systemctl is-active camxora-api
echo ALEMBIC_UPGRADE_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    _, stdout, stderr = client.exec_command(REMOTE, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
