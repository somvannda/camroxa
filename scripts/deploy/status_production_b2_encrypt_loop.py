#!/usr/bin/env python3
"""Show production B2 encrypt-loop status. Host 82.197.71.248 only."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

CMD = r"""
set -e
systemctl is-active camxora-b2-encrypt-loop || true
ps -p $(systemctl show camxora-b2-encrypt-loop -p MainPID --value) -o pid,etime,stat,pcpu --no-headers || echo DEAD
echo ===log===
sudo tail -n 12 /opt/camxora/tmp/production_mp3_backfill.log
echo ===counts===
sudo -u postgres psql -d camxora_platform -t -A <<'SQL'
SELECT 'music_mp3_leftover', COUNT(*) FROM suno_tasks
 WHERE source = 'web_music'
   AND (
     (COALESCE(package_status_ok, 'none') = 'none' AND COALESCE(b2_storage_key_ok, '') <> '')
     OR (COALESCE(package_status_alt, 'none') = 'none' AND COALESCE(b2_storage_key_alt, '') <> '')
   );
SELECT 'music_mp3_ready', COUNT(*) FROM suno_tasks
 WHERE source = 'web_music'
   AND (COALESCE(package_status_ok, 'none') = 'ready' OR COALESCE(package_status_alt, 'none') = 'ready');
SELECT 'studio_mp3_ready', COUNT(*) FROM suno_tasks
 WHERE COALESCE(source, 'studio') = 'studio'
   AND (COALESCE(package_status_ok, 'none') = 'ready' OR COALESCE(package_status_alt, 'none') = 'ready');
SELECT 'catalog_ready', COUNT(*) FROM stream_tracks WHERE COALESCE(package_status, 'none') = 'ready';
SELECT 'catalog_leftover', COUNT(*) FROM stream_tracks
 WHERE COALESCE(package_status, 'none') = 'none'
   AND storage_key IS NOT NULL AND storage_key <> '';
SELECT 'alembic', version_num FROM alembic_version;
SQL
curl -sS -m 3 -o /tmp/prod_health.json -w 'health=%{http_code}\n' http://127.0.0.1:8100/health || true
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != CANONICAL_PRODUCTION_HOST:
        print("REFUSE host", host)
        return 2
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=45)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
