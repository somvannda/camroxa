#!/usr/bin/env python3
"""Final read-only check: the new Signup Guard bundle is publicly served."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set -e
CHUNK=$(grep -rl "Signup Guard" /opt/camxora/repo/admin_portal/dist/assets 2>/dev/null | head -1)
echo "marker_chunk=$CHUNK"
echo "--- public fetch check ---"
FULL=$(curl -sS -m 12 "https://admin.camxora.com/assets/$(basename "$CHUNK")" 2>/dev/null | grep -c 'signup-domain-guard' || true)
echo "public_sg_hits=$FULL"
FULL2=$(curl -sS -m 12 "https://admin.camxora.com/assets/$(basename "$CHUNK")" 2>/dev/null | grep -c 'Signup Guard' || true)
echo "public_tab_hits=$FULL2"
if [ "$FULL" -ge 1 ] && [ "$FULL2" -ge 1 ]; then echo FINAL_SG_UI_OK; else echo FINAL_SG_UI_FAIL; exit 1; fi
"""


def run_cmd(client, cmd: str, timeout: int = 60) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=60), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
