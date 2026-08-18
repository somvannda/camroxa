#!/usr/bin/env python3
"""Read-only production check: web-music audio URLs vs B2 keys."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
echo '=== recent web_music tasks ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT id, left(title,40) AS title,
       round(duration_ok::numeric,2) AS dur_ok,
       round(duration_alt::numeric,2) AS dur_alt,
       b2_storage_key_ok, b2_storage_key_alt,
       left(audio_url_ok, 70) AS audio_ok,
       left(audio_url_alt, 70) AS audio_alt,
       left(audio_id_ok, 12) AS aid_ok,
       left(audio_id_alt, 12) AS aid_alt
FROM suno_tasks
WHERE source = 'web_music'
  AND (title ILIKE '%Fire in Our Bones%' OR title ILIKE '%sdfdsafdsa%' OR created_at > NOW() - INTERVAL '3 days')
ORDER BY created_at DESC
LIMIT 20;
"
echo '=== colliding b2 ok keys ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT b2_storage_key_ok, count(*) AS n, array_agg(left(title,30) ORDER BY created_at DESC) AS titles
FROM suno_tasks
WHERE source = 'web_music' AND COALESCE(b2_storage_key_ok,'') <> ''
GROUP BY 1
HAVING count(*) > 1
ORDER BY n DESC
LIMIT 20;
"
echo '=== colliding b2 alt keys ==='
sudo -u postgres psql -d camxora_platform -c "
SELECT b2_storage_key_alt, count(*) AS n, array_agg(left(title,30) ORDER BY created_at DESC) AS titles
FROM suno_tasks
WHERE source = 'web_music' AND COALESCE(b2_storage_key_alt,'') <> ''
GROUP BY 1
HAVING count(*) > 1
ORDER BY n DESC
LIMIT 20;
"
echo '=== deployed origin playback ==='
grep -n 'b2_storage_key_ok\|storage_key = f\"web-music\|song_title\|task_id' /opt/camxora/repo/platform_api/services/web_music_service.py | head -40
echo '=== deployed b2 key formula ==='
grep -n 'storage_key = ' /opt/camxora/repo/platform_api/services/streaming_upload_service.py | head -20
echo '=== built player replaceAudio ==='
grep -R -l 'replaceAudio' /opt/camxora/repo/music_web/.next 2>/dev/null | head -5
echo DIAG_DISTINCT_CLIP_DONE
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
