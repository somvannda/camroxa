#!/usr/bin/env python3
"""Locate: 'Encryption master key is not configured' source + SunoClient constructions."""
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
REPO=/opt/camxora/repo/platform_api
echo '=== [1] where is "Encryption master key is not configured" ==='
grep -rn 'Encryption master key is not configured' $REPO --include=*.py | grep -v '.bak' | head -10
echo
echo '=== [2] SunoClient( constructions ==='
grep -rn 'SunoClient()' $REPO --include=*.py | grep -v '.bak' | head -20
echo
echo '=== [3] content_audio_kek / encryption_master_key usage in config ==='
grep -n 'content_audio_kek\|encryption_master_key' $REPO/config.py | head -20
echo
echo '=== [4] runtime settings check (booleans only) ==='
cd $REPO && env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
from platform_api.config import get_settings
s = get_settings()
print("encryption_master_key set:", bool(getattr(s, "encryption_master_key", "")))
print("content_audio_kek set:", bool(getattr(s, "content_audio_kek", "")))
PYEOF
echo LOCATE_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
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
