#!/usr/bin/env python3
"""Production hotfix: iOS HLS playback + lock screen (allowlisted paths only)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

API_FILES = [
    "platform_api/config.py",
    "platform_api/main.py",
    "platform_api/wire_dependencies.py",
    "platform_api/middleware/auth.py",
    "platform_api/routers/web_music.py",
    "platform_api/routers/web_music_licenses.py",
    "platform_api/routers/streaming_public.py",
    "platform_api/routers/streaming_admin.py",
    "platform_api/routers/admin_user_web_music.py",
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/audio_packager.py",
    "platform_api/services/audio_package_service.py",
    "platform_api/services/content_license_service.py",
    "platform_api/services/decrypted_play_cache.py",
    "platform_api/services/forensic_watermark.py",
    "platform_api/services/hls_packager.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_catalog_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/batch_service.py",
    "platform_api/migrations/versions/107_protected_playback.py",
    "platform_api/migrations/versions/115_hls_playback.py",
]

MUSIC_WEB_FILES = [
    "music_web/package.json",
    "music_web/package-lock.json",
    "music_web/public/camxora-silent-hold.wav",
    "music_web/src/lib/camxora-decrypt.ts",
    "music_web/src/lib/content-license.ts",
    "music_web/src/lib/streaming-api.ts",
    "music_web/src/lib/web-music-api.ts",
    "music_web/src/lib/playlist-api.ts",
    "music_web/src/lib/mpeg-playback.ts",
    "music_web/src/lib/mpeg-sync.ts",
    "music_web/src/lib/mp3-software-decode.ts",
    "music_web/src/lib/media-session.ts",
    "music_web/src/lib/now-playing-debug.ts",
    "music_web/src/lib/crios-now-playing-debug.ts",
    "music_web/src/lib/vendor/mpg123/EmscriptenWasm.js",
    "music_web/src/lib/vendor/mpg123/MPEGDecoder.js",
    "music_web/src/lib/vendor/mpg123/WASMAudioDecoderCommon.js",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/components/home-gate.tsx",
]

ADMIN_FILES = [
    "admin_portal/src/hooks/use-playback-audit.ts",
    "admin_portal/src/pages/streaming/playback-audit.tsx",
    "admin_portal/src/pages/streaming/catalog.tsx",
    "admin_portal/src/hooks/use-streaming.ts",
    "admin_portal/src/App.tsx",
    "admin_portal/src/components/layout/sidebar.tsx",
]


def _run(client, cmd: str, timeout: int = 900) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out + ("\n" + err if err.strip() else "")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== iOS HLS playback -> production ({host}) ===", flush=True)

    all_files = API_FILES + MUSIC_WEB_FILES + ADMIN_FILES
    for rel in all_files:
        if not (ROOT / rel).is_file():
            raise SystemExit(f"Missing: {rel}")

    nginx_conf = DEPLOY / "nginx-camxora-production.conf"
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in all_files:
            sftp.put(str(ROOT / rel), f"/opt/camxora/repo/{rel}".replace("\\", "/"))
            print(f"Uploaded {rel}", flush=True)
        if nginx_conf.is_file():
            sftp.put(str(nginx_conf), "/tmp/nginx-camxora-production.conf")
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
command -v ffmpeg >/dev/null || (apt-get update -qq && apt-get install -y -qq ffmpeg)
REPO=/opt/camxora/repo
chown -R camxora:camxora $REPO/platform_api $REPO/music_web
rm -f $REPO/platform_api/migrations/versions/114_playback_event_detail.py
sed -i 's/114_playback_event_detail/109_playback_event_detail/g' $REPO/platform_api/migrations/versions/115_hls_playback.py
VER=$(sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;")
if [ "$VER" != "115_hls_playback" ]; then
  sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade 115_hls_playback'
fi
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
systemctl restart camxora-api
systemctl list-units --type=service --all --no-pager --plain 'camxora-worker*' \
  | awk '{print $1}' | grep -E '^camxora-worker' | while read -r u; do systemctl restart "$u" || true; done
sleep 4
systemctl is-active camxora-api
cp /tmp/nginx-camxora-production.conf /etc/nginx/sites-available/camxora-production
ln -sf /etc/nginx/sites-available/camxora-production /etc/nginx/sites-enabled/camxora-production
nginx -t && systemctl reload nginx
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm install && npm run build'
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
curl -sS -m 8 http://127.0.0.1:8100/api/v1/web-music/licenses/module-hash
echo
echo IOS_HLS_PRODUCTION_DONE
""",
        )
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
