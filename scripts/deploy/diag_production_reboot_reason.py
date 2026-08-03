#!/usr/bin/env python3
"""Investigate why production VPS rebooted."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo === BOOT ===
uptime -s
who -b
last -x | head -20
echo === PREVIOUS SHUTDOWN JOURNAL ===
journalctl -b -1 -n 80 --no-pager 2>/dev/null | tail -80
echo === CURRENT BOOT START ===
journalctl -b 0 -n 40 --no-pager | head -40
echo === KERNEL / PANIC BEFORE REBOOT ===
journalctl -b -1 -k --no-pager 2>/dev/null | grep -iE "panic|oops|BUG:|Out of memory|Watchdog|Hardware Error|MCE|reset|reboot" | tail -40
echo === UNATTENDED UPGRADES ===
ls -la /var/log/unattended-upgrades/ 2>/dev/null
tail -80 /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null
tail -40 /var/log/unattended-upgrades/unattended-upgrades-shutdown.log 2>/dev/null
echo === APT HISTORY AROUND REBOOT ===
grep -nE "Start-Date|End-Date|Commandline|Upgrade|Remove|Install" /var/log/apt/history.log 2>/dev/null | tail -60
echo === DPKG RECENT ===
tail -40 /var/log/dpkg.log 2>/dev/null
echo === SYSTEMD SHUTDOWN TARGET ===
journalctl -b -1 -u systemd-shutdown --no-pager 2>/dev/null | tail -30
journalctl -b -1 --priority=err --no-pager 2>/dev/null | tail -40
echo === CONTABO / CLOUD HINTS ===
dmesg -T 2>/dev/null | head -30
cat /etc/hostname
uname -a
echo REBOOT_DIAG_DONE
"""


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=180)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
