#!/usr/bin/env python3
"""Check encryption keys are configured in prod service/worker env (names only)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
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
echo '=== unit EnvironmentFiles / ExecStart (api + suno worker) ==='
for u in camxora-api camxora-worker-suno@1; do
  echo "--- $u ---"
  systemctl cat $u 2>/dev/null | grep -iE 'EnvironmentFile|Environment=|ExecStart|User=' | head -6
done
echo
echo '=== key NAMES present in env files (values hidden) ==='
for f in $(systemctl cat camxora-api 2>/dev/null | grep -oP 'EnvironmentFile=\K[^ ]+'); do
  echo "file: $f"
  grep -oE '^[A-Z_]+=' "$f" 2>/dev/null | sed 's/=$//' | grep -iE 'KEY|SECRET|KEK|MASTER|ENCRYPT|B2|STORAGE|DATABASE' | head -20
done
echo ENV_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
