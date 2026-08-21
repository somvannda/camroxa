#!/usr/bin/env python3
"""File-scoped sandbox hotfix: playlist detail Select/DropdownMenu UX (no full tarball)."""

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
    "music_web/src/components/playlist-detail-page-client.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== playlist detail UX -> sandbox ({host}) ===")

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

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora $REPO/music_web/src/components/playlist-detail-page-client.tsx
grep -n "MusicSelect\|DropdownMenu\|AlbumPlaybackControls\|Remove from playlist" \
  $REPO/music_web/src/components/playlist-detail-page-client.tsx
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
BUILD=$(cat /opt/camxora/repo/music_web/.next/BUILD_ID)
echo BUILD_ID=$BUILD
echo PLAYLIST_DETAIL_UX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
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
        if "PLAYLIST_DETAIL_UX_DONE" not in out:
            raise SystemExit("Sandbox playlist detail UX hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
