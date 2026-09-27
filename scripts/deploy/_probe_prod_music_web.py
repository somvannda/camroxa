#!/usr/bin/env python3
"""READ-ONLY: verify production music_web rebuild + service."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo '--- camxora-music active ---'
systemctl is-active camxora-music
systemctl show camxora-music -p ExecMainStartTimestamp -p MainPID
echo '--- build id / mtime ---'
ls -la --time-style=+%Y-%m-%dT%H:%M:%S /opt/camxora/repo/music_web/.next/BUILD_ID 2>/dev/null
cat /opt/camxora/repo/music_web/.next/BUILD_ID 2>/dev/null; echo
echo '--- site health ---'
curl -sk -o /dev/null -w 'http=%{http_code}\n' https://music.camxora.com/ || true
echo '--- marker in built chunks (monthly free credits) ---'
grep -rl "credits left this month" /opt/camxora/repo/music_web/.next/static 2>/dev/null | head -2 || echo NO_MARKER
echo PROBE_MUSIC_WEB_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 90) -> str:
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
        print(run_cmd(client, CMD, timeout=80), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
