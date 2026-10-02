#!/usr/bin/env python3
"""Read-only: confirm how the admin portal is served + new bundle reachable."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
echo '=== systemd units mentioning admin/camxora ==='
systemctl list-units --all 2>/dev/null | grep -iE 'admin|camxora|portal' | head -20 || true
echo '=== nginx admin root ==='
grep -rn "admin_portal\|admin.camxora\|camxora-admin" /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -20 || true
echo '=== dist index asset ==='
grep -oE 'assets/index-[A-Za-z0-9_-]+\.js' /opt/camxora/repo/admin_portal/dist/index.html | head -3
echo '=== served via https? probe domains ==='
for h in admin.camxora.com camxora.com; do
  echo "-- $h --"
  curl -sS -m 8 -o /dev/null -w 'status=%{http_code}\n' "https://$h/" 2>&1 | head -1
done
echo '=== journal admin marker via static index (admin host) ==='
curl -sS -m 8 https://admin.camxora.com/ 2>/dev/null | grep -oE 'assets/index-[A-Za-z0-9_-]+\.(js|css)' | head -5 || true
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
