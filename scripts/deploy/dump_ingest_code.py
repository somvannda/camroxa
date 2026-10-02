#!/usr/bin/env python3
"""Save targeted code ranges from prod for local reading."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "ingest_code.txt"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r'''
set +e
REPO=/opt/camxora/repo/platform_api
echo '=========== job_types.py FULL ==========='
cat $REPO/services/job_types.py
echo '=========== worker.py HEAD 120 ==========='
sed -n '1,120p' $REPO/worker.py
echo '=========== worker.py handler map grep ==========='
grep -n 'def handle\|JOB_\|register\|dispatch\|process_' $REPO/worker.py | head -60
echo '=========== streaming_upload 400-560 ==========='
sed -n '400,560p' $REPO/services/streaming_upload_service.py
echo '=========== streaming_upload 900-1140 ==========='
sed -n '900,1140p' $REPO/services/streaming_upload_service.py
echo '=========== streaming_upload 1500-1760 ==========='
sed -n '1500,1760p' $REPO/services/streaming_upload_service.py
echo '=========== callbacks.py 120-260 ==========='
sed -n '120,260p' $REPO/routers/callbacks.py
echo 'CODE_DUMP_END'
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        print(f"Saved {LOCAL}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
