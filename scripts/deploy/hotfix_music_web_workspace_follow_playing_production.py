#!/usr/bin/env python3
"""File-scoped production hotfix: Create workspace play/title/WAV UX.

Uploads allowlisted files only. Does not sync a full platform_api tree.
Does not run alembic upgrade heads or npm ci.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
SCRIPT_DIR = Path(__file__).resolve().parent
_DEPLOY_CANDIDATES = [PRIMARY / "scripts" / "deploy", SCRIPT_DIR]
for candidate in _DEPLOY_CANDIDATES:
    venv_site = candidate / ".venv" / "Lib" / "site-packages"
    if venv_site.is_dir():
        sys.path.insert(0, str(venv_site))
    if (candidate / "deploy.py").is_file():
        sys.path.insert(0, str(candidate))
        break

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = [
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/playing-equalizer.tsx",
    "music_web/src/lib/web-music-api.ts",
    "music_web/src/app/globals.css",
    "music_web/next.config.ts",
    "platform_api/services/web_music_service.py",
    "platform_api/services/suno_audio_resolver.py",
    "platform_api/clients/suno_client.py",
    "platform_api/routers/web_music.py",
    "platform_api/migrations/versions/105_web_music_clip_titles.py",
]


def _run(client, cmd: str, timeout: int = 480) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/music_web/src/components/playing-equalizer.tsx \
  $REPO/music_web/src/lib/web-music-api.ts \
  $REPO/music_web/src/app/globals.css \
  $REPO/music_web/next.config.ts \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py \
  $REPO/platform_api/clients/suno_client.py \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/migrations/versions/105_web_music_clip_titles.py

echo '=== wav/title columns ==='
timeout 20 sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c "
ALTER TABLE suno_tasks
  ADD COLUMN IF NOT EXISTS title_ok TEXT,
  ADD COLUMN IF NOT EXISTS title_alt TEXT,
  ADD COLUMN IF NOT EXISTS wav_task_id_ok TEXT,
  ADD COLUMN IF NOT EXISTS wav_task_id_alt TEXT,
  ADD COLUMN IF NOT EXISTS wav_url_ok TEXT,
  ADD COLUMN IF NOT EXISTS wav_url_alt TEXT,
  ADD COLUMN IF NOT EXISTS wav_status_ok TEXT,
  ADD COLUMN IF NOT EXISTS wav_status_alt TEXT,
  ADD COLUMN IF NOT EXISTS b2_wav_storage_key_ok TEXT,
  ADD COLUMN IF NOT EXISTS b2_wav_storage_key_alt TEXT,
  ADD COLUMN IF NOT EXISTS audio_id_ok TEXT,
  ADD COLUMN IF NOT EXISTS audio_id_alt TEXT;
"

echo '=== import check ==='
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.suno_audio_resolver import validate_wav_bytes, download_suno_wav_bytes; from platform_api.clients.suno_client import parse_suno_wav_poll; from platform_api.services.audio_origin_proxy import is_missing_range; print('IMPORT_OK', parse_suno_wav_poll({'code':404}))"

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/prod_health.json || true
echo
test "$code" = "200"

echo '=== rebuild music_web ==='
API_URL=https://api.camxora.com
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  TURNSTILE_SITE=\$(grep -m1 '^CLOUDFLARE_TURNSTILE_SITE_KEY=' $REPO/platform_api/.env | cut -d= -f2- || true)
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://camxora.com
NEXT_PUBLIC_CAMXORA_ENV=production
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=\$TURNSTILE_SITE
ENVEOF
  npm run build
"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo WORKSPACE_FOLLOW_PLAYING_PROD_DONE
""",
            timeout=900,
        )
        try:
            print(out)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        log_path = SCRIPT_DIR / "deploy-music-web-workspace-follow-playing-production.log"
        log_path.write_text(out, encoding="utf-8")
        if code != 0 or "WORKSPACE_FOLLOW_PLAYING_PROD_DONE" not in out:
            raise SystemExit("Production follow-playing hotfix did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
