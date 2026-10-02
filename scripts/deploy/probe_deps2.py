#!/usr/bin/env python3
"""Fetch prod dependencies.py bodies for pool/generation/ai_routing wiring."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "dependencies.bodies.txt"
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
REPO=/opt/camxora/repo/platform_api
echo '=== lines 55-110 (db_pool/redis) ==='
sed -n '55,110p' $REPO/dependencies.py
echo '=== lines 385,470 (generation svc) ==='
sed -n '385,470p' $REPO/dependencies.py
echo '=== lines 740,830 (ai routing + credit v2) ==='
sed -n '740,830p' $REPO/dependencies.py
echo BODIES_DONE
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
        LOCAL.parent.mkdir(parents=True, exist_ok=True)
        LOCAL.write_text(out, encoding="utf-8")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
