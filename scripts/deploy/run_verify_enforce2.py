#!/usr/bin/env python3
"""Two-phase enforcement verify: schedule (short) -> local wait -> after-state."""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL_SCHEDULE = ROOT / ".dbg" / "live-probe" / "verify_enforce_schedule.py"
LOCAL_CHECK = ROOT / ".dbg" / "live-probe" / "verify_enforce_check.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
WAIT_S = int(sys.argv[1]) if len(sys.argv) > 1 else 240

SCHEDULE_CMD = (
    "cd /opt/camxora/repo/platform_api\n"
    "env PYTHONPATH=/opt/camxora/repo .venv/bin/python /tmp/verify_enforce_schedule.py 2>&1\n"
)
CHECK_CMD = (
    "cd /opt/camxora/repo/platform_api\n"
    "env PYTHONPATH=/opt/camxora/repo .venv/bin/python /tmp/verify_enforce_check.py {task} 2>&1\n"
)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/verify_enforce_schedule.py", "wb") as rf:
            rf.write(LOCAL_SCHEDULE.read_bytes())
        with sftp.file("/tmp/verify_enforce_check.py", "wb") as rf:
            rf.write(LOCAL_CHECK.read_bytes())
        sftp.close()

        print("=== phase 1: schedule wav+lrc on a wav-gappy task ===")
        _, stdout, stderr = client.exec_command(SCHEDULE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        m = re.search(r"TASK_ID=([0-9a-fA-F-]{36})", out)
        if not m:
            print("NO_TASK_ID_FOUND")
            return 1
        task = m.group(1)

        print(f"=== waiting {WAIT_S}s for conversion + B2 upload ===")
        time.sleep(WAIT_S)

        print("=== phase 2: after-state ===")
        _, stdout, stderr = client.exec_command(
            CHECK_CMD.format(task=task), get_pty=False, timeout=180
        )
        out2 = stdout.read().decode("utf-8", errors="replace")
        err2 = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out2.encode("utf-8", errors="replace"))
        if err2.strip():
            sys.stderr.write("STDERR2: " + err2[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
