#!/usr/bin/env python3
"""Run a specific alembic revision on sandbox (avoids multi-head 'head' issues)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

REV = "075_batch_channel_pipeline_complete"

REMOTE = f"""
set -e
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade {REV}'
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT column_name FROM information_schema.columns WHERE table_name='batch_channel_assets' AND column_name='pipeline_complete';"
systemctl is-active camxora-api
echo ALEMBIC_UPGRADE_DONE
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    _, stdout, stderr = client.exec_command(REMOTE, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
