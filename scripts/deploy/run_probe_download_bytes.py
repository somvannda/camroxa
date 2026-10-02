#!/usr/bin/env python3
"""Upload + run probe_download_bytes.py on prod."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "probe_download_bytes.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
TASKS = str(sys.argv[1]) if len(sys.argv) > 1 else "6e80e724,05e6a13c,804f81c3,0cb1a116"

REMOTE_CMD = (
    "cd /opt/camxora/repo/platform_api\n"
    f"env PYTHONPATH=/opt/camxora/repo .venv/bin/python -u /tmp/probe_download_bytes.py {TASKS} 2>&1\n"
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/probe_download_bytes.py", "wb") as rf:
            rf.write(LOCAL.read_bytes())
        sftp.close()
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
