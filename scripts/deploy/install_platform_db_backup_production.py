#!/usr/bin/env python3
"""Install/update the nightly platform-database backup on production.

Uploads ``platform-db-backup.sh`` + its systemd units, enables the 04:00 timer
and runs one dump so the unit is proven green.

    python scripts/deploy/install_platform_db_backup_production.py
"""

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
REPO = "/opt/camxora/repo"
SCRIPT_REMOTE = f"{REPO}/scripts/deploy/platform-db-backup.sh"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(DEPLOY / "platform-db-backup.sh"), "/tmp/camxora-platform-db-backup.sh")
        sftp.put(
            str(DEPLOY / "systemd" / "camxora-platform-db-backup.service"),
            "/tmp/camxora-platform-db-backup.service",
        )
        sftp.put(
            str(DEPLOY / "systemd" / "camxora-platform-db-backup.timer"),
            "/tmp/camxora-platform-db-backup.timer",
        )
        sftp.close()

        remote = f"""
set -e
bash -n /tmp/camxora-platform-db-backup.sh
install -m 755 -o camxora -g camxora /tmp/camxora-platform-db-backup.sh {SCRIPT_REMOTE}.new
mv -f {SCRIPT_REMOTE}.new {SCRIPT_REMOTE}
install -m 644 /tmp/camxora-platform-db-backup.service /etc/systemd/system/
install -m 644 /tmp/camxora-platform-db-backup.timer /etc/systemd/system/
# /opt/camxora/backups is root-owned; the unit runs as camxora.
install -d -m 750 -o camxora -g camxora /opt/camxora/backups/platform
systemctl daemon-reload
systemctl enable --now camxora-platform-db-backup.timer
systemctl start camxora-platform-db-backup.service
systemctl status camxora-platform-db-backup.service --no-pager -l | head -12
systemctl list-timers camxora-platform-db-backup.timer --no-pager | head -3
ls -la /opt/camxora/backups/platform/ | tail -4
"""
        _, stdout, stderr = client.exec_command(remote, get_pty=True, timeout=1800)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
