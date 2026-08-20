#!/usr/bin/env python3
"""File-scoped production hotfix: iOS packaged playback + Create packaged-only play.

Uploads licenses router, Create ingest/playability, and music_web player files only.
Host must be 82.197.71.248. Does not tar platform_api or admin.
"""

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
    "platform_api/routers/web_music_licenses.py",
    "platform_api/services/web_music_storage_keys.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/audio_package_service.py",
]

MUSIC_WEB_FILES = [
    "music_web/src/components/player-provider.tsx",
    "music_web/src/components/player-bar.tsx",
    "music_web/src/lib/camxora-decrypt.ts",
    "music_web/src/lib/content-license.ts",
    "music_web/src/lib/ios-playback.ts",
    "music_web/src/lib/media-session.ts",
    "music_web/src/app/layout.tsx",
    "music_web/public/camxora-now-playing.png",
    "music_web/public/apple-touch-icon.png",
]

FILES = API_FILES + MUSIC_WEB_FILES


def _run(client, cmd: str, timeout: int = 600) -> tuple[int, str]:
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

    for rel in FILES:
        if not (ROOT / rel).is_file():
            raise SystemExit(f"Missing source file: {rel}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}".replace("\\", "/")
            parent = remote.rsplit("/", 1)[0]
            _, stdout, _ = client.exec_command(f"mkdir -p {parent}")
            stdout.channel.recv_exit_status()
            print(f"Uploading {rel}", flush=True)
            sftp.put(str(ROOT / rel), remote)
        sftp.close()

        chown = " ".join(f"/opt/camxora/repo/{p}" for p in FILES)
        print("=== restart API + rebuild music_web ===", flush=True)
        code, out = _run(
            client,
            rf"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora {chown}
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo music_http=$(curl -sS -o /dev/null -w '%{{http_code}}' -H 'CF-IPCountry: KH' https://music.camxora.com/)
echo api_http=$(curl -sS -o /dev/null -w '%{{http_code}}' -H 'CF-IPCountry: KH' https://api.camxora.com/health)
sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && set +a && cd /opt/camxora/repo && /opt/camxora/repo/platform_api/.venv/bin/python -c "from platform_api.services.web_music_service import WebMusicService; from platform_api.services.web_music_storage_keys import web_music_object_key; print(\"import_ok\")"'
echo MUSIC_WEB_IOS_PLAYBACK_PRODUCTION_DONE
""",
            timeout=300,
        )
        text = out[-8000:] if len(out) > 8000 else out
        sys.stdout.buffer.write(text.encode("ascii", errors="replace") + b"\n")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
