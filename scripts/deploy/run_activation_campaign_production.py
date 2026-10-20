#!/usr/bin/env python3
"""Operator driver: run the activation-link campaign on production.

Dry run (default):

    python scripts/deploy/run_activation_campaign_production.py

Send for real:

    python scripts/deploy/run_activation_campaign_production.py --apply

Optional filters are forwarded to the server script: ``--only EMAIL`` (repeatable),
``--limit N``, ``--force``, ``--delay S``. Uploads the sender to /tmp so a code
deploy is not required just to recover affected accounts.
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
REMOTE_SCRIPT = DEPLOY / "send_activation_links.py"
REMOTE_PATH = "/tmp/send_activation_links.py"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    forwarded = " ".join(sys.argv[1:])
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(REMOTE_SCRIPT), REMOTE_PATH)
        sftp.close()
        remote = (
            "cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo/ /opt/camxora/repo/platform_api/.venv/bin/python "
            f"{REMOTE_PATH} {forwarded}"
        )
        _, stdout, stderr = client.exec_command(remote, get_pty=True, timeout=900)
        while True:
            chunk = stdout.read(4096)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
