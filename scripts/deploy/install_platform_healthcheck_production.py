#!/usr/bin/env python3
"""Install/update the platform-wide health probe on production.

Uploads ``platform-healthcheck.sh`` + its systemd units, enables the 5-minute
timer, runs one probe immediately and prints its result.

    python scripts/deploy/install_platform_healthcheck_production.py
    python scripts/deploy/install_platform_healthcheck_production.py --digest
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
REPO = "/opt/camxora/repo"
SCRIPT_REMOTE = f"{REPO}/scripts/deploy/platform-healthcheck.sh"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    digest = "--digest" in sys.argv
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        # Upload to /tmp and install by rename: writing straight onto the live
        # path lets a timer run read a half-written script (seen 2026-10-21,
        # "syntax error near unexpected token" mid-install).
        sftp.put(str(DEPLOY / "platform-healthcheck.sh"), "/tmp/camxora-platform-healthcheck.sh")
        sftp.put(
            str(DEPLOY / "systemd" / "camxora-platform-healthcheck.service"),
            "/tmp/camxora-platform-healthcheck.service",
        )
        sftp.put(
            str(DEPLOY / "systemd" / "camxora-platform-healthcheck.timer"),
            "/tmp/camxora-platform-healthcheck.timer",
        )
        sftp.close()

        remote = f"""
set -e
bash -n /tmp/camxora-platform-healthcheck.sh
install -m 755 -o camxora -g camxora /tmp/camxora-platform-healthcheck.sh {SCRIPT_REMOTE}.new
mv -f {SCRIPT_REMOTE}.new {SCRIPT_REMOTE}
install -m 644 /tmp/camxora-platform-healthcheck.service /etc/systemd/system/
install -m 644 /tmp/camxora-platform-healthcheck.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now camxora-platform-healthcheck.timer
systemctl start camxora-platform-healthcheck.service || true
systemctl list-timers camxora-platform-healthcheck.timer --no-pager | head -3
journalctl -u camxora-platform-healthcheck.service --since '2 minutes ago' --no-pager | tail -20
"""
        _, stdout, stderr = client.exec_command(remote, get_pty=True, timeout=240)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
        if digest:
            cmd = f"sudo -u camxora bash -lc 'bash {SCRIPT_REMOTE} --digest-now'"
            _, dout, derr = client.exec_command(cmd, get_pty=True, timeout=120)
            print(dout.read().decode("utf-8", errors="replace"))
            e = derr.read().decode("utf-8", errors="replace")
            if e.strip():
                print(e, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
