#!/usr/bin/env python3
"""Repair production content_key_id to match CXA1 headers (Duke first, then multi-key)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")
if not (HOST_REPO / ".deploy" / "secrets.production.env").is_file():
    HOST_REPO = CODE_ROOT
DEPLOY = HOST_REPO / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_PY = CODE_ROOT / "scripts" / "deploy" / "_repair_content_key_id_from_cxa_remote.py"
REMOTE_PATH = "/tmp/repair_content_key_id_from_cxa.py"


def main() -> int:
    email = (sys.argv[1] if len(sys.argv) > 1 else "iamduke1987@gmail.com").strip()
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== repair content_key_id {email} -> {host} ===", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(REMOTE_PY), REMOTE_PATH)
        sftp.close()
        remote_arg = "" if email in {"", "all", "--all"} else email
        cmd = (
            "sudo -u camxora bash -lc "
            "'cd /opt/camxora/repo && set -a && source platform_api/.env && "
            "unset PLATFORM_CORS_ORIGINS && set +a && "
            f"PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {REMOTE_PATH} {remote_arg}'"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        while not stdout.channel.exit_status_ready():
            time.sleep(1)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if err.strip():
            sys.stdout.write(err)
        if "KEY_REPAIR_DONE" not in out:
            raise SystemExit("Key repair did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
