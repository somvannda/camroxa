#!/usr/bin/env python3
"""Check sandbox timezone vs audit log timestamps."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
echo '=== OS timezone ==='
timedatectl | grep -E 'Time zone|Local time|Universal time'
echo '=== camxora-api TZ ==='
systemctl show camxora-api -p Environment --no-pager | tr ' ' '\n' | grep ^TZ= || true
echo '=== PostgreSQL timezone ==='
sudo -u postgres psql -d camxora_platform -tAc "SHOW timezone;"
sudo -u postgres psql -d camxora_platform -tAc "SELECT now(), now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'Asia/Phnom_Penh';"
echo '=== latest audit rows ==='
sudo -u postgres psql -d camxora_platform -c "SELECT created_at, created_at AT TIME ZONE 'UTC' AS utc_wall, created_at AT TIME ZONE 'Asia/Phnom_Penh' AS pp_wall FROM audit_logs ORDER BY created_at DESC LIMIT 5;"
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, _ = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
