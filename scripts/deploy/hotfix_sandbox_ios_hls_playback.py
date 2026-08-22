#!/usr/bin/env python3
"""Sandbox hotfix: AES-128 HLS lane (API migration + backfill + music_web)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages",):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/migrations/versions/115_hls_playback.py",
    "platform_api/services/hls_packager.py",
    "platform_api/services/audio_package_service.py",
    "platform_api/services/content_license_service.py",
    "platform_api/routers/web_music_licenses.py",
    "platform_api/services/audio_origin_proxy.py",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/lib/mpeg-playback.ts",
    "music_web/src/lib/streaming-api.ts",
    "music_web/src/lib/content-license.ts",
    "music_web/src/lib/media-session.ts",
    "music_web/src/lib/mp3-software-decode.ts",
    "music_web/public/camxora-silent-hold.wav",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== iOS HLS AES-128 -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        chown_list = " ".join(f"$REPO/{rel.replace(chr(92), '/')}" for rel in FILES)
        cmd = rf"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora {chown_list}

command -v ffmpeg >/dev/null || {{
  echo "Installing ffmpeg..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ffmpeg
}}
command -v ffmpeg >/dev/null || (echo FFMPEG_MISSING && exit 1)
ffmpeg -version | head -n 1

sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && .venv/bin/alembic upgrade 115_hls_playback'

systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music

sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && unset PLATFORM_CORS_ORIGINS && set +a && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python - <<"PY"
import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")

import asyncpg
from platform_api.services.audio_package_service import AudioPackageService


async def main() -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    try:
        svc = AudioPackageService(pool)
        for _ in range(5):
            result = await svc.backfill_hls(limit=10)
            print("backfill_hls", result)
            if int(result.get("ready") or 0) == 0:
                break
    finally:
        await pool.close()


asyncio.run(main())
PY'

echo IOS_HLS_PLAYBACK_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
