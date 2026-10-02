#!/usr/bin/env python3
"""Read-only: list prod paths for admin API + admin portal."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
echo '=== repo top ==='
ls /opt/camxora/repo | head -40
echo '=== platform_api routers ==='
ls /opt/camxora/repo/platform_api/routers 2>/dev/null | head -60
echo '=== admin-ish routers ==='
ls /opt/camxora/repo/platform_api/routers 2>/dev/null | grep -i admin
echo '=== services generation_freeze ==='
ls /opt/camxora/repo/platform_api/services 2>/dev/null | grep -iE 'freeze|suspend|block'
echo '=== admin_portal ==='
ls /opt/camxora/repo/admin_portal/src/pages/settings 2>/dev/null
ls /opt/camxora/repo/admin_portal/src/hooks 2>/dev/null | head -40
echo '=== where is admin router served (main mounts) ==='
python3 - <<'PY'
from pathlib import Path
p = Path('/opt/camxora/repo/platform_api/main.py')
t = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
print('HAS admin include', 'admin' in t.lower())
for line in t.splitlines():
    if 'admin' in line.lower() or 'include_router' in line.lower() or 'mount' in line.lower():
        print(line[:180])
PY
"""


def run_cmd(client, cmd: str, timeout: int = 40) -> str:
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
        print(run_cmd(client, CMD, timeout=40), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
