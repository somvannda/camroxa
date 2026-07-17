#!/usr/bin/env python3
"""Fetch API logs matching users/errors."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> None:
    secrets = load_secrets()
    client = ssh_connect(
        secrets["VPS_HOST"],
        secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("VPS_PASSWORD") or None,
    )
    cmd = (
        "journalctl -u camxora-api -n 500 --no-pager | "
        "grep -iE 'users|email_verif|traceback|error|exception' | tail -40"
    )
    _, stdout, _ = client.exec_command(cmd)
    sys.stdout.buffer.write(stdout.read())
    client.close()


if __name__ == "__main__":
    main()
