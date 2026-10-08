#!/usr/bin/env python3
"""Run the stranded-alt recovery on production.

Usage:
    python scripts/deploy/run_web_music_alt_recover_production.py            # dry-run probe
    python scripts/deploy/run_web_music_alt_recover_production.py --apply    # recover all
    python scripts/deploy/run_web_music_alt_recover_production.py --apply --limit 5
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
DEPLOY = CODE_ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_PY = CODE_ROOT / "scripts" / "deploy" / "_web_music_alt_recover_remote.py"
REMOTE_PATH = "/tmp/web_music_alt_recover.py"


def main() -> int:
    remote_args = " ".join(sys.argv[1:])
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== stranded-alt recovery -> {host} args={remote_args!r} ===", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(REMOTE_PY), REMOTE_PATH)
        sftp.close()
        cmd = (
            "sudo -u camxora bash -lc "
            f"'cd /opt/camxora/repo && set -a && source platform_api/.env && "
            "unset PLATFORM_CORS_ORIGINS && set +a && "
            f"PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {REMOTE_PATH} {remote_args}'"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=2400)
        while not stdout.channel.exit_status_ready():
            time.sleep(1)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
        if "ALT_RECOVER_DONE" not in out:
            raise SystemExit("Recovery did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
