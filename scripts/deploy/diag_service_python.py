#!/usr/bin/env python3
"""Read-only: locate camxora-api service interpreter + confirm service config."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
systemctl cat camxora-api | grep -E 'ExecStart|WorkingDirectory|EnvironmentFile'
echo '---'
ls -la /opt/camxora/ 2>/dev/null | head -30
echo '---'
ls /opt/camxora/*/bin/python* 2>/dev/null
ls /opt/camxora/venv/bin/python* 2>/dev/null
find /opt/camxora -maxdepth 3 -name 'python*' -path '*/bin/*' 2>/dev/null | head
echo '---'
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT 'guard count bowlfuel.com' AS label, count(*)::int AS n
FROM users u
WHERE u.deleted_at IS NULL AND u.status='active'
  AND lower(split_part(u.email,'@',2))='bowlfuel.com'
  AND 'music_web' = ANY(u.products)
  AND NOT EXISTS (SELECT 1 FROM licenses l WHERE l.user_id=u.id AND l.status='active');
"
"""


def run_cmd(client, cmd: str, timeout: int = 45) -> str:
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
        print(run_cmd(client, CMD, timeout=45), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
