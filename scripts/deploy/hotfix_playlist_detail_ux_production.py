#!/usr/bin/env python3
"""File-scoped production hotfix: playlist detail Select/DropdownMenu UX.

Uploads only playlist-detail-page-client.tsx. Does not replace playlist-add
files (add-to-playlist-button, memberships, create-page, web_music_service).
Does not sync a full music_web tarball.

Secrets load from the main checkout's scripts/deploy + .deploy if this
worktree has no production env file.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_DEPLOY = Path(r"D:\Development\Projects\Electron\MusicGenerator\scripts\deploy")
DEPLOY_CANDIDATES = [MAIN_DEPLOY, ROOT / "scripts" / "deploy"]
for candidate in DEPLOY_CANDIDATES:
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
    "music_web/src/components/playlist-detail-page-client.tsx",
]
KEEP_MARKERS = [
    "list_playlist_memberships",
    "playlists/memberships",
    "PlaylistMembershipsProvider",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== playlist detail UX -> production ({host}) ===")

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
            payload = local.read_bytes().replace(b"\r\n", b"\n")
            with sftp.file(remote, "wb") as rf:
                rf.write(payload)
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
echo '--- keep playlist-add markers before rebuild ---'
grep -n 'list_playlist_memberships\|playlists/memberships' $REPO/platform_api/routers/web_music.py $REPO/platform_api/services/web_music_service.py | head
grep -n 'PlaylistMembershipsProvider\|ClipPlaylistNames' \
  $REPO/music_web/src/app/layout.tsx \
  $REPO/music_web/src/components/add-to-playlist-button.tsx \
  $REPO/music_web/src/components/create-page-client.tsx | head
grep -n "MusicSelect\|DropdownMenu\|Remove from playlist" \
  $REPO/music_web/src/components/playlist-detail-page-client.tsx | head
chown camxora:camxora $REPO/music_web/src/components/playlist-detail-page-client.tsx
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 8
systemctl is-active camxora-music
echo '--- keep playlist-add markers after rebuild ---'
grep -n 'list_playlist_memberships\|playlists/memberships' $REPO/platform_api/routers/web_music.py $REPO/platform_api/services/web_music_service.py | head
grep -n 'PlaylistMembershipsProvider' $REPO/music_web/src/app/layout.tsx | head
BUILD=$(cat /opt/camxora/repo/music_web/.next/BUILD_ID)
echo BUILD_ID=$BUILD
curl -sS -o /dev/null -w 'music=%{http_code}\n' --max-time 20 https://music.camxora.com/playlists || true
echo PLAYLIST_DETAIL_UX_PROD_DONE
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
        for marker in KEEP_MARKERS:
            if marker not in out:
                raise SystemExit(f"Production playlist-add marker missing after deploy: {marker}")
        if "PLAYLIST_DETAIL_UX_PROD_DONE" not in out:
            raise SystemExit("Production playlist detail UX hotfix did not finish cleanly.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
