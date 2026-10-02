#!/usr/bin/env python3
"""Production hotfix: surface real backend/Suno 5xx errors in music_web.

Previously the create client replaced any 502/503/504 whose text looked like a
gateway error with the generic "AI assist is temporarily unavailable..." copy,
hiding the real Suno reason (rate limit / maintenance / etc.). Now the real API
message is shown whenever the response body carried one; the generic copy only
applies when the body had no usable message (nginx-level outage).

Backs up, uploads music_web/src/lib/web-music-api.ts, rebuilds music_web on the
server, restarts camxora-music, verifies. NO git commit / merge.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
LOCAL = ROOT / ".dbg" / "prod-musicweb-lib" / "web-music-api.ts"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE = "/opt/camxora/repo/music_web/src/lib/web-music-api.ts"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP="%STAMP%"
cp -p $REPO/music_web/src/lib/web-music-api.ts $REPO/music_web/src/lib/web-music-api.ts.pre-surface-err-$STAMP.bak
chown -R camxora:camxora $REPO/music_web/src
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
curl -s -o /dev/null -w "music=%{http_code}\n" -m 5 http://127.0.0.1:3102/ || echo MUSIC_FAIL
echo "--- built marker (real-message logic) ---"
grep -rl "Surface the API" $REPO/music_web/.next/static 2>/dev/null | head -2 || echo NO_MARKER
grep -rl "AI assist is temporarily unavailable" $REPO/music_web/.next/static 2>/dev/null | head -2 || true
journalctl -u camxora-music --since "2 minutes ago" --no-pager 2>/dev/null | grep -iE "Traceback|Failed to compile|ERROR" | tail -5 || true
echo SURFACE_SUNO_ERROR_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    if not LOCAL.is_file():
        raise FileNotFoundError(LOCAL)
    print(f"=== Surface real Suno errors -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file(REMOTE, "wb") as remote_file:
            remote_file.write(LOCAL.read_bytes())
        sftp.close()
        print(f"Uploaded {LOCAL.as_posix()} -> {REMOTE}")
        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "SURFACE_SUNO_ERROR_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
