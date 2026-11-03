#!/usr/bin/env python3
"""Install/update the CamXora ops monitor on production.

Uploads ``ops-alert.sh`` + its systemd units, enables the 5-minute timer, runs
one probe and prints the result. Also removes the legacy server-only
``/opt/camxora/bin/ops-alert.sh`` so the versioned copy is the only source.

    python scripts/deploy/install_ops_alert_production.py
    python scripts/deploy/install_ops_alert_production.py --send-status
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
SCRIPT_REMOTE = f"{REPO}/scripts/deploy/ops-alert.sh"
LEGACY_SCRIPT = "/opt/camxora/bin/ops-alert.sh"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    send_status = "--send-status" in sys.argv
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        # Upload to /tmp and install by rename: writing straight onto the live
        # path lets a timer read a half-written script.
        sftp.put(str(DEPLOY / "ops-alert.sh"), "/tmp/camxora-ops-alert.sh")
        sftp.put(
            str(DEPLOY / "systemd" / "ops-alert.service"),
            "/tmp/ops-alert.service",
        )
        sftp.put(
            str(DEPLOY / "systemd" / "ops-alert.timer"),
            "/tmp/ops-alert.timer",
        )
        sftp.close()

        remote = f"""
set -e
bash -n /tmp/camxora-ops-alert.sh
install -m 755 -o camxora -g camxora /tmp/camxora-ops-alert.sh {SCRIPT_REMOTE}.new
mv -f {SCRIPT_REMOTE}.new {SCRIPT_REMOTE}
install -m 644 /tmp/ops-alert.service /etc/systemd/system/
install -m 644 /tmp/ops-alert.timer /etc/systemd/system/
# The previous alert script lived only on the host; the versioned copy in the
# repo is now authoritative.
if [ -f {LEGACY_SCRIPT} ]; then
  mv -f {LEGACY_SCRIPT} {LEGACY_SCRIPT}.removed-$(date -u +%Y%m%dT%H%M%SZ)
fi
# Drop state left by the retired user-portal check (old `svc-*` keys).
rm -f /var/lib/camxora-ops-alert/svc-camxora-portal
systemctl daemon-reload
systemctl enable --now ops-alert.timer
systemctl start ops-alert.service || true
systemctl list-timers ops-alert.timer --no-pager | head -3
journalctl -u ops-alert.service --since '2 minutes ago' --no-pager | tail -20
echo '--- current status ---'
DRY_RUN=1 {SCRIPT_REMOTE} --dry-run || true
"""
        _, stdout, stderr = client.exec_command(remote, get_pty=True, timeout=300)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)

        if send_status:
            cmd = f"bash {SCRIPT_REMOTE} --status"
            _, sout, serr = client.exec_command(cmd, get_pty=True, timeout=120)
            print(sout.read().decode("utf-8", errors="replace"))
            e = serr.read().decode("utf-8", errors="replace")
            if e.strip():
                print(e, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
