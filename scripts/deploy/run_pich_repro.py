#!/usr/bin/env python3
"""Upload + run the pich reproduction probe on prod (real submission)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "probe_pich_generate.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/tmp/probe_pich_generate.py"

REMOTE_CMD = r"""
set -e
chmod 644 /tmp/probe_pich_generate.py
cd /opt/camxora/repo/platform_api
env PYTHONPATH=/opt/camxora/repo .venv/bin/python /tmp/probe_pich_generate.py 2>&1
echo PROBE_EXIT_CODE=$?
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL.is_file():
        raise FileNotFoundError(LOCAL)
    print(f"=== run pich repro probe -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE, "wb") as rf:
            rf.write(LOCAL.read_bytes())
        sftp.close()
        print(f"Uploaded {LOCAL.name} -> {REMOTE}")

        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0 if "PROBE_EXIT_CODE=0" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
