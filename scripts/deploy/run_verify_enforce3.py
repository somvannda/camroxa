#!/usr/bin/env python3
"""Detached enforcement verify: nohup full probe on prod, poll its log for the result."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "verify_enforce.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
LOG = "/tmp/verify_enforce_run.log"
MAX_SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 480

START_CMD = (
    "cd /opt/camxora/repo/platform_api\n"
    f"rm -f {LOG}\n"
    "nohup env PYTHONPATH=/opt/camxora/repo .venv/bin/python -u /tmp/verify_enforce.py "
    f"> {LOG} 2>&1 < /dev/null &\n"
    "echo DETACHED_PID=$!\n"
)
TAIL_CMD = f"tail -c 6000 {LOG} 2>/dev/null || echo LOG_MISSING\n"


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/verify_enforce.py", "wb") as rf:
            rf.write(LOCAL.read_bytes())
        sftp.close()

        _, stdout, _ = client.exec_command(START_CMD, get_pty=False, timeout=60)
        start_out = stdout.read().decode("utf-8", errors="replace")
        print(start_out.strip())

        print(f"=== polling {LOG} (up to {MAX_SECONDS}s) ===")
        seen = ""
        deadline = time.time() + MAX_SECONDS
        while time.time() < deadline:
            time.sleep(45)
            _, stdout, _ = client.exec_command(TAIL_CMD, get_pty=False, timeout=60)
            chunk = stdout.read().decode("utf-8", errors="replace")
            if chunk and chunk != seen:
                new = chunk[len(seen):] if chunk.startswith(seen) else chunk
                sys.stdout.buffer.write(new.encode("utf-8", errors="replace"))
                sys.stdout.flush()
                seen = chunk
            if "VERIFY_ENFORCE_DONE" in chunk or "NO_GAPPY_TASK" in chunk or "Traceback" in chunk:
                print("=== verify finished ===")
                return 0
        print("=== timed out waiting for log completion ===")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
