#!/usr/bin/env python3
"""Production read-only: B2 clip hashes, deployed mint URLs, stream route status."""

from __future__ import annotations

import sys
import time
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent
sys.path.insert(0, str(DEPLOY / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
REMOTE_PY = "/tmp/diag_b2_clips.py"
LOCAL_PY = DEPLOY / "_remote_diag_b2_clips.py"

CMD = r"""
set +e
echo '=== mint urls deployed ==='
grep -n 'generations/.*/stream' /opt/camxora/repo/platform_api/services/web_music_service.py | head -10
echo '=== stream routes deployed ==='
grep -n 'stream/{variant}\|def stream_generation' /opt/camxora/repo/platform_api/routers/web_music.py | head -10
echo '=== music_web bundle stream path ==='
grep -R -l 'stream/ok' /opt/camxora/repo/music_web/.next 2>/dev/null | head -5
echo '=== curl stream routes (expect 401 not 404) ==='
for path in \
  /api/v1/web-music/generations/a41873ce-3956-4377-9032-5ac0e5b88ca8/stream/ok \
  /api/v1/web-music/generations/a41873ce-3956-4377-9032-5ac0e5b88ca8/stream/alt \
  '/api/v1/web-music/generations/a41873ce-3956-4377-9032-5ac0e5b88ca8/stream?variant=ok'
do
  code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:8100$path" || true)
  echo "$code $path"
done
echo '=== B2 hashes ==='
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_b2_clips.py'
echo DIAG_DONE
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
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        sftp.put(str(LOCAL_PY), REMOTE_PY)
        sftp.close()
        print(run_cmd(client, CMD, timeout=50), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
