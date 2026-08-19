#!/usr/bin/env python3
"""Read-only sandbox check: web-music lyric/style assist setup."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect

CMD = r"""
set +e
echo '=== credit_pricing web_music ==='
sudo -u postgres psql -d camxora_platform -c "SELECT ai_service, operation_type, COALESCE(sub_model,'') AS model, credits_per_operation, needs_review FROM credit_pricing WHERE operation_type IN ('web_music_style','web_music_lyrics') ORDER BY 2,1,3;"
echo '=== ai_routing web_music ==='
sudo -u postgres psql -d camxora_platform -Atc "SELECT COALESCE(value::text,'') FROM system_settings WHERE key = 'ai_routing_assignments';" | python3 -c "
import json,sys
raw=sys.stdin.read().strip()
data=json.loads(raw) if raw else {}
for key in ('web_music_lyrics','web_music_style','lyric'):
    print(key, '=', json.dumps(data.get(key)))
"
echo '=== key pool ==='
sudo -u postgres psql -d camxora_platform -c "SELECT provider, status, count(*) FROM api_key_entries WHERE provider IN ('openai','deepseek','slai') GROUP BY 1,2 ORDER BY 1,2;"
echo '=== style request ==='
grep -n "class WebMusicStyleRequest\|lyrics: str = Field" /opt/camxora/repo/platform_api/routers/web_music.py | head -10
echo SANDBOX_DONE
"""


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Read-only check on {user}@{host}", flush=True)
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
    print(out.decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
