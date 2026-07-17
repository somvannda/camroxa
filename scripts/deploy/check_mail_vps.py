#!/usr/bin/env python3
"""Check VPS mail server readiness (Postfix, ports, PTR, outbound 25)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def run(client, cmd: str) -> str:
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out or err


def main() -> int:
    secrets = load_secrets()
    host = secrets["VPS_HOST"]
    client = ssh_connect(
        host,
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )

    checks = [
        ("hostname", "hostname -f"),
        ("ip", "ip -4 addr show scope global | awk '/inet /{print $2}'"),
        ("postfix", "dpkg -l postfix 2>/dev/null | awk '/^ii/{print $2,$3}' || echo not-installed"),
        ("opendkim", "dpkg -l opendkim opendkim-tools 2>/dev/null | awk '/^ii/{print $2,$3}' || echo not-installed"),
        ("listening", "ss -lntp 2>/dev/null | awk 'NR==1 || /:25 |:587 |:465 /'"),
        ("outbound25", f"timeout 6 bash -c 'echo QUIT | nc -w4 gmail-smtp-in.l.google.com 25' 2>&1 | head -2"),
        ("ptr", f"dig +short -x {host} 2>/dev/null || true"),
        ("ufw", "ufw status 2>/dev/null | head -5 || echo ufw-not-active"),
    ]
    for label, cmd in checks:
        print(f"[{label}]")
        print(run(client, cmd))
        print()

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
