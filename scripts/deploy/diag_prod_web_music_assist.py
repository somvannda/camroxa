#!/usr/bin/env python3
"""Read-only production check: web-music lyric/style assist setup."""

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
echo '=== alembic ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT version_num FROM alembic_version ORDER BY 1;"
echo '=== credit_pricing web_music ==='
sudo -u postgres psql -d camxora_platform -c "SELECT ai_service, operation_type, COALESCE(sub_model,'') AS model, credits_per_operation, needs_review FROM credit_pricing WHERE operation_type IN ('web_music_style','web_music_lyrics') ORDER BY operation_type, ai_service, sub_model;"
echo '=== ai_routing web_music ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT COALESCE(value::text,'') FROM system_settings WHERE key = 'ai_routing_assignments';" | python3 -c "
import json,sys
raw=sys.stdin.read().strip()
print('RAW_LEN', len(raw))
if not raw:
    print('NO_ASSIGNMENTS_ROW'); raise SystemExit
data=json.loads(raw)
for key in ('web_music_lyrics','web_music_style','lyric'):
    print(key, '=', json.dumps(data.get(key)))
"
echo '=== key pool counts ==='
sudo -u postgres psql -d camxora_platform -c "SELECT provider, status, count(*) FROM api_key_entries WHERE provider IN ('openai','deepseek','slai') GROUP BY 1,2 ORDER BY 1,2;"
echo '=== deployed style request ==='
grep -n "class WebMusicStyleRequest\|lyrics: str = Field\|generate-styles\|generate-draft" /opt/camxora/repo/platform_api/routers/web_music.py | head -20
echo '=== music nginx ==='
awk '/server_name music.camxora.com/,/^}/' /etc/nginx/sites-available/camxora-production
echo DIAG_WEB_MUSIC_ASSIST_DONE
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
    print(f"Read-only check on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    print("SSH connected", flush=True)
    try:
        print(run_cmd(client, CMD, timeout=40), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
