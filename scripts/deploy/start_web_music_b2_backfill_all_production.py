#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HOST_REPO = Path(r"D:\Development\Projects\Electron\MusicGenerator")
DEPLOY = HOST_REPO / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect  # noqa: E402

CMD = r"""
set +e
echo === START ===
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && unset PLATFORM_CORS_ORIGINS && set +a && PYTHONPATH=/opt/camxora/repo nohup platform_api/.venv/bin/python /tmp/web_music_b2_backfill_stuck.py all >/tmp/web_music_b2_backfill_all.log 2>&1 </dev/null & echo pid=$!'
sleep 2
echo === PS ===
ps -eo pid,etime,cmd | grep -E 'web_music_b2_backfill_stuck' | grep -v grep
echo === LOG ===
head -20 /tmp/web_music_b2_backfill_all.log
echo DONE
"""


def main() -> int:
    host, user, password = resolve_production_ssh(load_production_secrets())
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        chan = client.get_transport().open_session()
        chan.settimeout(30)
        chan.exec_command(CMD)
        out = b""
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
        sys.stdout.buffer.write(out)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
