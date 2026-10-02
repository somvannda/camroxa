#!/usr/bin/env python3
"""Read suno_audio_resolver 150-280 + who calls fetch_timestamped_lrc_with_pool."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "resolver.txt"
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
echo '=== suno_audio_resolver.py 150-280 ==='
sed -n '150,280p' $REPO/services/suno_audio_resolver.py
echo
echo '=== SunoClient.__init__ signature ==='
grep -n -A 8 'class SunoClient' $REPO/clients/suno_client.py | head -20
echo
echo '=== def fetch_timestamped_lrc_with_pool (where) ==='
grep -rn 'def fetch_timestamped_lrc_with_pool' $REPO --include=*.py | head
echo RESOLVER_DONE
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
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
