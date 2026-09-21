#!/usr/bin/env python3
"""Run the auto-retry plumbing check on prod (root, env loaded)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
CHECK = DEPLOY / "_check_auto_retry_prod.py"

CMD = r'''
cat > /tmp/check_auto_retry.py <<'PY'
%CHECK_BODY%
PY
(cd /opt/camxora/repo && env PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -B /tmp/check_auto_retry.py)
echo CHECK_RUNNER_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print("Refusing: prod check.\n  python scripts/deploy/run_auto_retry_check_production.py --i-mean-production")
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = CMD.replace("%CHECK_BODY%", CHECK.read_text(encoding="utf-8").replace("\r\n", "\n"))
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-1500:])
        if "CHECK_OK" not in out:
            print("\nCheck FAILED")
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
