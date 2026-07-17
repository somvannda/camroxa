#!/usr/bin/env python3
"""Rebuild admin portal on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )
    _, stdout, stderr = client.exec_command(
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'",
        timeout=300,
    )
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out:
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err:
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    code = stdout.channel.recv_exit_status()
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
