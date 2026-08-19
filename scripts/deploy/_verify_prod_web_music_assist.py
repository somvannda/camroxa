#!/usr/bin/env python3
from __future__ import annotations

import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(SCRIPT_DIR))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
CMD = r"""
set +e
echo '=== style request ==='
grep -n "class WebMusicStyleRequest\|lyrics: str = Field" /opt/camxora/repo/platform_api/routers/web_music.py | head -10
echo '=== assist helper ==='
grep -n "reraise_text_assist_failure\|_AI_ASSIST_UNAVAILABLE" /opt/camxora/repo/platform_api/services/web_music_service.py | head -10
echo '=== duration still present ==='
grep -n "duration_seconds\|duration_ok" /opt/camxora/repo/platform_api/routers/web_music.py /opt/camxora/repo/platform_api/services/web_music_service.py | head -8
echo '=== frontend ==='
grep -n "temporarily unavailable\|slice(0, 400)\|Add style tags" /opt/camxora/repo/music_web/src/lib/web-music-api.ts /opt/camxora/repo/music_web/src/components/create-page-client.tsx | head -15
echo '=== services ==='
systemctl is-active camxora-api
systemctl is-active camxora-music
curl -sS -o /dev/null -w 'health=%{http_code}\n' --max-time 10 http://127.0.0.1:8100/health
curl -sS -o /dev/null -w 'music=%{http_code}\n' --max-time 15 https://music.camxora.com/create
echo VERIFY_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    chan = client.get_transport().open_session()
    chan.settimeout(40)
    chan.exec_command(CMD)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            out += chan.recv(65535)
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > 40:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    sys.stdout.buffer.write(out)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
