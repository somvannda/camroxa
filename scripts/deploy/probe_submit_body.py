#!/usr/bin/env python3
"""Dump create-page-client.tsx submit body construction (lines 725-800) + router schema."""
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

REMOTE_CMD = r"""
set +e
MW=/opt/camxora/repo/music_web/src
echo '=== create-page-client.tsx 720-800 (submit payload) ==='
sed -n '720,800p' $MW/components/create-page-client.tsx
echo
echo '=== 405-435 (state defaults incl model) ==='
sed -n '405,435p' $MW/components/create-page-client.tsx
echo
echo '=== backend schema vocal_gender + model + literals ==='
grep -n 'vocal_gender\|style_weight\|model:\|Literal' /opt/camxora/repo/platform_api/routers/web_music.py | head -20
echo SUBMIT_PROBE_DONE
"""


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
            sys.stderr.write("STDERR: " + err[-1200:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
