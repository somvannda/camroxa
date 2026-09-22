#!/usr/bin/env python3
"""Run the read-only upload-job pagination SQL smoke on prod."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
SMOKE = DEPLOY / "_smoke_upload_paging.py"

CMD = r'''
sudo -u camxora bash -lc "cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python /tmp/smoke_upload_paging.py"
echo SMOKE_RUNNER_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print("Refusing: prod smoke.\n  python scripts/deploy/run_upload_paging_smoke_production.py --i-mean-production")
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/smoke_upload_paging.py", "wb") as remote_file:
            remote_file.write(SMOKE.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.write(err[-1500:].encode("utf-8", errors="replace") + b"\n")
        if "SMOKE_OK" not in out:
            print("\nSQL smoke FAILED")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
