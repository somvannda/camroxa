#!/usr/bin/env python3
"""Sandbox hotfix: iOS Now Playing diagnostics + in-DOM media listener bind."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

MUSIC_WEB_FILES = [
    "music_web/src/components/player-provider.tsx",
    "music_web/src/lib/mpeg-playback.ts",
    "music_web/src/lib/media-session.ts",
    "music_web/src/lib/now-playing-debug.ts",
    "music_web/src/lib/crios-now-playing-debug.ts",
    "music_web/src/lib/content-license.ts",
]

API_FILES = [
    "platform_api/services/content_license_service.py",
]


def upload_files(sftp, rel_paths: list[str]) -> None:
    for rel in rel_paths:
        local = ROOT / rel
        if not local.is_file():
            raise FileNotFoundError(local)
        remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
        with sftp.file(remote, "wb") as rf:
            rf.write(local.read_bytes())
        print(f"Uploaded {rel}")


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        upload_files(sftp, MUSIC_WEB_FILES)
        upload_files(sftp, API_FILES)
        sftp.close()
        cmd = """
set -e
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-api
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-api
systemctl is-active camxora-music
echo IOS_NOW_PLAYING_DIAG_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=420)
        out = stdout.read()
        err = stderr.read()
        sys.stdout.buffer.write(out)
        if err.strip():
            sys.stderr.buffer.write(err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
