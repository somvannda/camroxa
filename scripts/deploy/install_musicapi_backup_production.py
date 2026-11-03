#!/usr/bin/env python3
"""Install/update the nightly Music API backup script on production.

The systemd unit runs ``/opt/camxora/repo/scripts/deploy/musicapi-backup.sh``
by absolute path. That file lives outside ``DEPLOY_DIRS``, so a tarball deploy
used to delete it and the timer then failed with status 127. This installer
uploads the script and runs one backup to prove the unit is green.

    python scripts/deploy/install_musicapi_backup_production.py
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
SCRIPT_REMOTE = f"{REPO}/scripts/deploy/musicapi-backup.sh"


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
        sftp.put(str(DEPLOY / "musicapi-backup.sh"), "/tmp/camxora-musicapi-backup.sh")
        sftp.close()

        remote = f"""
set -e
bash -n /tmp/camxora-musicapi-backup.sh
install -m 755 -o camxora -g camxora /tmp/camxora-musicapi-backup.sh {SCRIPT_REMOTE}.new
mv -f {SCRIPT_REMOTE}.new {SCRIPT_REMOTE}
systemctl start camxora-musicapi-backup.service
systemctl status camxora-musicapi-backup.service --no-pager -l | head -12
ls -la /opt/camxora/backups/musicapi/ | tail -4
"""
        _, stdout, stderr = client.exec_command(remote, get_pty=True, timeout=600)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
