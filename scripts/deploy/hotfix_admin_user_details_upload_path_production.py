#!/usr/bin/env python3
"""File-scoped production hotfix: restore upload_path_exists import on users.py.

Do not upload local users.py — production has later avatar/music-credit fields.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

REMOTE = r"""
set -e
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/camxora/repo/platform_api/routers/users.py")
text = path.read_text(encoding="utf-8")
old = "from platform_api.utils.upload_paths import resolve_upload_path, uploads_root\n"
new = "from platform_api.utils.upload_paths import resolve_upload_path, uploads_root, upload_path_exists\n"
if new in text:
    print("ALREADY_PATCHED")
elif old not in text:
    raise SystemExit("IMPORT_LINE_MISSING")
else:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("PATCHED")
PY
chown camxora:camxora /opt/camxora/repo/platform_api/routers/users.py
grep -n 'upload_paths import' /opt/camxora/repo/platform_api/routers/users.py
python3 -m py_compile /opt/camxora/repo/platform_api/routers/users.py
echo COMPILE_OK
systemctl restart camxora-api
sleep 8
systemctl is-active camxora-api
curl -sS -o /tmp/prod_health.json -w 'HEALTH_%{http_code}\n' --max-time 12 http://127.0.0.1:8100/health || true
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
        if chan.recv_stderr_ready():
            out += chan.recv_stderr(65535)
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            while chan.recv_stderr_ready():
                out += chan.recv_stderr(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.05)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"File-scoped production hotfix on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("SSH connected", flush=True)
    try:
        print(run_cmd(client, REMOTE, timeout=80), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
