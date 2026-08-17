#!/usr/bin/env python3
"""Add suno_tasks duration columns on sandbox without a full alembic upgrade.

Sandbox alembic currently cannot resolve `head` (missing revision
`084_provider_balance_events` in a merge). This applies the 104 DDL only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

REMOTE = r"""
set -e
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c "
ALTER TABLE suno_tasks
  ADD COLUMN IF NOT EXISTS duration_ok DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS duration_alt DOUBLE PRECISION;
"
sudo -u postgres psql -d camxora_platform -t -A -c "
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'suno_tasks'
  AND column_name IN ('duration_ok', 'duration_alt')
ORDER BY 1;
"
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
echo DURATION_COLUMNS_DONE
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target sandbox host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    _, stdout, stderr = client.exec_command(REMOTE, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.write(out)
    if err.strip():
        sys.stdout.write(err)
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
