#!/usr/bin/env python3
"""Production subscription/license transfer runner (probe/apply).

Read-only by default. Only writes with --apply. Refuses non-production hosts.

  python scripts/deploy/run_subscription_transfer_production.py --i-mean-production
  python scripts/deploy/run_subscription_transfer_production.py --i-mean-production --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

REMOTE_PY = DEPLOY / "_subscription_transfer.py"


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(
            "Usage:\n"
            "  python scripts/deploy/run_subscription_transfer_production.py --i-mean-production\n"
            "  python scripts/deploy/run_subscription_transfer_production.py --i-mean-production --apply\n"
            "Refusing to run. This touches the production licenses table."
        )
        return 2
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host} MODE={'apply' if apply else 'probe'}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/subscription_transfer.py", "wb") as remote:
            remote.write(REMOTE_PY.read_bytes().replace(b"\r\n", b"\n"))
        sftp.close()
        mode = "apply" if apply else "probe"
        cmd = f"""
set -e
if ! ip -4 addr | grep -q '82.197.71.248'; then
  echo Refusing non-production host
  exit 1
fi
if ip -4 addr | grep -q '46.250.235.83'; then
  echo Refusing sandbox host
  exit 1
fi
sudo -u camxora bash -lc "cd /opt/camxora/repo && source platform_api/.venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && MODE={mode} python /tmp/subscription_transfer.py"
echo SUBSCRIPTION_TRANSFER_RUNNER_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if apply and "APPLY_DONE" not in out:
            raise SystemExit("Subscription transfer did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
