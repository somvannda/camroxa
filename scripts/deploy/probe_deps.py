#!/usr/bin/env python3
"""Probe prod dependencies.py: get_db_pool / get_v2_credit_service / get_generation_service shapes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "live-probe" / "dependencies.grep.txt"
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
echo '=== defs ==='
grep -nE '^def get_db_pool|^def get_redis|^def get_generation_service|^def get_v2_credit_service|^def get_ai_routing_service|^def get_credit_pricing_service|def get_db_pool|def get_v2_credit_service|def get_generation_service' $REPO/dependencies.py | head -20
echo '=== get_db_pool body ==='
awk '/def get_db_pool/,/^def [a-zA-Z_]+\(/' $REPO/dependencies.py | head -25
echo '=== get_v2_credit_service body ==='
awk '/def get_v2_credit_service/,/^def [a-zA-Z_]+\(/' $REPO/dependencies.py | head -30
echo DEPS_GREP_DONE
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
