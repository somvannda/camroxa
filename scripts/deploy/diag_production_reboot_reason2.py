#!/usr/bin/env python3
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
echo === APT AUTO REBOOT CONF ===
grep -Rns Automatic-Reboot /etc/apt/apt.conf.d/ 2>/dev/null
grep -Rns InstallOnShutdown /etc/apt/apt.conf.d/ 2>/dev/null
echo === REBOOT REQUIRED FLAG ===
ls -la /var/run/reboot-required /var/run/reboot-required.pkgs 2>/dev/null
cat /var/run/reboot-required.pkgs 2>/dev/null
echo === INSTALLED KERNELS ===
dpkg -l 'linux-image-6.8.0-*' 2>/dev/null | awk '/^ii/ {print}'
echo === UNATTENDED LOG ===
tail -120 /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null
echo === SHUTDOWN LOG ===
tail -80 /var/log/unattended-upgrades/unattended-upgrades-shutdown.log 2>/dev/null
echo === PREV BOOT REBOOT LINES ===
journalctl -b -1 --no-pager 2>/dev/null | grep -iE 'Starting Reboot|reboot.target|Requested transaction|Unattended|Need to reboot|linux-image' | tail -50
echo DONE
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
        _, stdout, _ = client.exec_command(CMD, get_pty=True, timeout=120)
        print(stdout.read().decode(errors="replace"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
