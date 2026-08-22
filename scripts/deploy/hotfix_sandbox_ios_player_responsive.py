#!/usr/bin/env python3
"""File-scoped sandbox hotfix: iOS progressive Web Audio + Media Session."""

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
    "music_web/public/camxora-silent-hold.wav",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/lib/mpeg-playback.ts",
    "music_web/src/lib/mp3-software-decode.ts",
    "music_web/src/lib/media-session.ts",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== iOS player responsive -> sandbox ({host}) ===")

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
chown camxora:camxora {chown_list}

grep -n "StreamingMp3Decoder\|assignPlayerSilentHold\|updateMediaSession\|first_audio_ms" \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/lib/mpeg-playback.ts \
  $REPO/music_web/src/lib/mp3-software-decode.ts \
  $REPO/music_web/src/lib/media-session.ts | head -n 40

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
echo IOS_PLAYER_RESPONSIVE_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=420)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        try:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            print("remote output unprintable")
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
