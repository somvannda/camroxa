#!/usr/bin/env python3
"""Inspect sandbox users and clear auth lockouts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
echo '=== user count ==='
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT COUNT(1) FROM users;"
echo '=== recent users ==='
sudo -u postgres psql -d camxora_platform -c "SELECT email, role, is_active, created_at FROM users ORDER BY created_at DESC LIMIT 15;"
echo '=== lockout tables ==='
sudo -u postgres psql -d camxora_platform -c "\dt *lock*"
sudo -u postgres psql -d camxora_platform -c "\dt *login*"
sudo -u postgres psql -d camxora_platform -c "\dt *attempt*"
echo '=== redis keys login ==='
redis-cli -n 1 KEYS '*lock*' 2>/dev/null | head -20
redis-cli -n 1 KEYS '*login*' 2>/dev/null | head -20
redis-cli -n 1 KEYS '*auth*' 2>/dev/null | head -20
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err[:800])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
