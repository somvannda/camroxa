#!/usr/bin/env python3
"""Run stuck web-music B2 backfill on production for one user or the queue."""

from __future__ import annotations

import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = Path(r"D:\Development\Projects\Electron\MusicGenerator")
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
REMOTE_PY = CODE_ROOT / "scripts" / "deploy" / "_web_music_b2_backfill_stuck_remote.py"
REMOTE_PATH = "/tmp/web_music_b2_backfill_stuck.py"


def main() -> int:
    email = (sys.argv[1] if len(sys.argv) > 1 else "all").strip()
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== stuck B2 backfill {email} -> {host} ===", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(REMOTE_PY), REMOTE_PATH)
        sftp.close()
        remote_arg = "" if email in {"", "all", "--all"} else email
        cmd = (
            "sudo -u camxora bash -lc "
            f"'cd /opt/camxora/repo && set -a && source platform_api/.env && "
            "unset PLATFORM_CORS_ORIGINS && set +a && "
            f"PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {REMOTE_PATH} {remote_arg}'"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=2400)
        while not stdout.channel.exit_status_ready():
            time.sleep(1)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
        if "BACKFILL_DONE" not in out:
            raise SystemExit("Backfill did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
