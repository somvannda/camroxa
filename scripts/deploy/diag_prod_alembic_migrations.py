#!/usr/bin/env python3
"""Quick production alembic / migration file diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = r"""
echo '=== alembic_version ==='
sudo -u postgres psql -d camxora_platform -t -A -c 'SELECT version_num FROM alembic_version;'
echo '=== 084 files ==='
ls /opt/camxora/repo/platform_api/migrations/versions/084* 2>/dev/null || echo NONE
echo '=== provider balance ==='
ls /opt/camxora/repo/platform_api/migrations/versions/*provider*balance* 2>/dev/null || echo NONE
echo '=== alembic heads (if possible) ==='
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic heads 2>&1 | tail -5' || true
"""
    _, stdout, _ = client.exec_command(remote, get_pty=True)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
