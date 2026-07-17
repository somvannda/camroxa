#!/usr/bin/env python3
"""Verify live nginx has 300s API proxy timeouts (prevents generate-logo 504)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_nginx import ENV_CONFIG  # noqa: E402
from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=("sandbox", "production"), default="sandbox")
    args = parser.parse_args()

    secrets = load_secrets()
    host = secrets.get("PRODUCTION_VPS_HOST") if args.env == "production" else secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    site = ENV_CONFIG[args.env]["remote_site"]

    client = ssh_connect(host, user, ensure_deploy_key(), secrets.get("VPS_PASSWORD") or None)
    _, stdout, _ = client.exec_command(f"grep -n proxy_read_timeout {site} 2>/dev/null || true")
    text = stdout.read().decode("utf-8", errors="replace")
    client.close()

    print(text)
    api_timeouts = [line for line in text.splitlines() if "300s" in line]
    ws_timeouts = [line for line in text.splitlines() if "86400" in line]

    if len(api_timeouts) < 3:
        print(f"FAIL: expected at least 3 proxy_read_timeout 300s lines in {site}, found {len(api_timeouts)}")
        return 1
    if not ws_timeouts:
        print("WARN: no WebSocket proxy_read_timeout 86400 found (optional but recommended)")

    print(f"OK: nginx API timeouts verified for {args.env} ({host})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
