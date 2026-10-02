#!/usr/bin/env python3
"""Prod hotfix v5: Suno title max 120 -> 80.

Root cause (reproduced live): WebMusicService.generate() with empty Title field
derives the title from the Lyrics first line and clamps to _WEB_MUSIC_TITLE_MAX
(120). Suno's actual hard limit is 80 chars; titles of 81-120 chars are rejected
with "The length of music title cannot exceed 80 characters", which fires AFTER
the 10-credit debit and causes the immediate refund + no suno_tasks row (pich's
exact signature when he pastes descriptive text into Lyrics without a Title).

Fix: _WEB_MUSIC_TITLE_MAX = 80 in web_music_suno_guard.py (single source that
both prepare_web_music_title() clamp and is_valid_web_music_title() validation
use). Applied surgically to the running prod file (backup first, no upload of
whole file to avoid tree drift). No git.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
STAMP = time.strftime("%Y%m%d-%H%M%S")

REMOTE_CMD = f"""
set -e
REPO=/opt/camxora/repo/platform_api
FILE=$REPO/services/web_music_suno_guard.py
echo '=== [1] current constant ==='
grep -n '_WEB_MUSIC_TITLE_MAX = ' $FILE
echo '=== [2] backup ==='
cp -p $FILE $FILE.pre-title80-{STAMP}.bak
echo "backup: $FILE.pre-title80-{STAMP}.bak"
echo '=== [3] apply 120 -> 80 ==='
sed -i 's/_WEB_MUSIC_TITLE_MAX = 120/_WEB_MUSIC_TITLE_MAX = 80/' $FILE
chown camxora:camxora $FILE
echo '=== [4] confirm ==='
grep -n '_WEB_MUSIC_TITLE_MAX = ' $FILE
$REPO/.venv/bin/python -m py_compile $FILE && echo COMPILE_OK
echo '=== [5] restart + health ==='
systemctl restart camxora-api
sleep 10
systemctl is-active camxora-api || true
curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' -m 10 http://127.0.0.1:8100/health || echo API_FAIL
journalctl -u camxora-api --since '2 minutes ago' --no-pager 2>/dev/null | grep -iE 'Traceback|Started server process|ImportError|ModuleNotFoundError' | tail -8 || true
echo FIX_TITLE80_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== Suno title max 120->80 -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        if "FIX_TITLE80_DONE" not in out or "api_health=200" not in out or "_WEB_MUSIC_TITLE_MAX = 80" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
