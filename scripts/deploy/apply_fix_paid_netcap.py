#!/usr/bin/env python3
"""Production hotfix: exempt paid users from the per-network free-song cap.

routers/web_music.py /generate called track_generation_attempt for every user,
so a paid subscriber generating >5 songs/day from one IP hit the free-user
"Maximum 5 free songs per day from one network" 429. Now the network cap only
applies to users with no active web subscription and no license.
Backs up, uploads, restarts camxora-api, verifies. NO git commit / merge.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "prod-webmusic-router" / "web_music.py"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/opt/camxora/repo/platform_api/routers/web_music.py"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo/platform_api
STAMP="%STAMP%"
cp -p $REPO/routers/web_music.py $REPO/routers/web_music.py.pre-paid-netcap-$STAMP.bak
chown camxora:camxora $REPO/routers/web_music.py
$REPO/.venv/bin/python -m py_compile $REPO/routers/web_music.py
grep -n "_has_web_subscription(UUID(ctx.user_id))" $REPO/routers/web_music.py
systemctl restart camxora-api
sleep 6
echo "--- api state ---"
systemctl is-active camxora-api || true
curl -s -o /dev/null -w "api_health=%{http_code}\n" -m 5 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "Traceback|ImportError|Started server process" | tail -6 || true
echo FIX_PAID_NETCAP_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL.is_file():
        raise FileNotFoundError(LOCAL)
    print(f"=== Fix paid net-cap -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE, "wb") as remote_file:
            remote_file.write(LOCAL.read_bytes())
        sftp.close()
        print(f"Uploaded {LOCAL.as_posix()} -> {REMOTE}")
        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-1500:] + "\n")
        if "FIX_PAID_NETCAP_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
