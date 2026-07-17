#!/usr/bin/env python3
"""Clear sandbox auth lockouts after deploy restarts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
echo '=== users ==='
sudo -u postgres psql -d camxora_platform -t -A -F'|' -c "SELECT email, role FROM users ORDER BY email;"
echo '=== lockout keys before ==='
redis-cli -n 1 KEYS 'auth:*' | sort
echo '=== clearing lockouts ==='
redis-cli -n 1 KEYS 'auth:lockout:*' | xargs -r redis-cli -n 1 DEL
redis-cli -n 1 KEYS 'auth:failures:*' | xargs -r redis-cli -n 1 DEL
echo '=== lockout keys after ==='
redis-cli -n 1 KEYS 'auth:*' | sort
echo LOCKOUTS_CLEARED
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[:500])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
