#!/usr/bin/env python3
"""Read-only: inspect blocked-list row state (count, updated_at, airhemp entry)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT key, value_type, updated_at,
       json_array_length(value::json) AS n,
       value::json ? 'airhemp.com' AS has_airhemp,
       value::json ? 'sgtelegramprobe.invalid' AS has_probe,
       value::json ? 'sgprobe.invalid' AS has_sgprobe
FROM system_settings WHERE key = 'signup_blocked_email_domains';
"
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT jsonb_array_elements_text(value::jsonb) AS domain
FROM system_settings WHERE key = 'signup_blocked_email_domains'
ORDER BY 1;
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
