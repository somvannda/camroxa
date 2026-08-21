#!/usr/bin/env python3
"""File-scoped sandbox hotfix: protected playback fast-start (no full music_web tarball).

Uploads only this task's API + player files from the fast-start worktree.
Secrets/SSH come from the sibling MusicGenerator checkout when this worktree
has no .deploy/secrets.sandbox.env.
"""

from __future__ import annotations

import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = CODE_ROOT.parent / "MusicGenerator"
if not (HOST_REPO / ".deploy" / "secrets.sandbox.env").is_file():
    HOST_REPO = CODE_ROOT
DEPLOY = HOST_REPO / "scripts" / "deploy"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages",):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
FILES = [
    "platform_api/services/encrypted_package_cache.py",
    "platform_api/services/audio_packager.py",
    "platform_api/routers/web_music_licenses.py",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/lib/mp3-software-decode.ts",
    "music_web/src/lib/mpeg-playback.ts",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== protected playback fast-start -> sandbox ({host}) ===")
    print(f"Code root: {CODE_ROOT}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = CODE_ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/encrypted_package_cache.py \
  $REPO/platform_api/services/audio_packager.py \
  $REPO/platform_api/routers/web_music_licenses.py \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/lib/mp3-software-decode.ts \
  $REPO/music_web/src/lib/mpeg-playback.ts

grep -n "get_packaged_blob\|encrypted_chunk_record\|FETCH_CONCURRENCY\|startFirst\|Mp3PcmDecoder\|first_audio_ms\|webaudio_ram" \
  $REPO/platform_api/routers/web_music_licenses.py \
  $REPO/platform_api/services/encrypted_package_cache.py \
  $REPO/music_web/src/components/player-provider.tsx \
  $REPO/music_web/src/lib/mpeg-playback.ts \
  $REPO/music_web/src/lib/mp3-software-decode.ts

test -f $REPO/music_web/src/components/brand-lockup.tsx
grep -q -- '--music-menu-clearance' $REPO/music_web/src/app/globals.css

systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"

sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
echo FAST_START_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        stdout.channel.settimeout(600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        try:
            print(out)
        except UnicodeEncodeError:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            try:
                print(err)
            except UnicodeEncodeError:
                print(err.encode("ascii", errors="replace").decode("ascii"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
