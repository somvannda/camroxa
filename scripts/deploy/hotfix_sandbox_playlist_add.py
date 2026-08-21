#!/usr/bin/env python3
"""File-scoped sandbox hotfix: playlist add packaged-ready + Create tick/chips.

Uploads allowlisted files only. Keeps sandbox phone viewport in layout.tsx.
Does not sync a full platform_api or music_web tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
UPLOADS = [
    "music_web/src/components/add-to-playlist-button.tsx",
    "music_web/src/components/playlist-memberships-provider.tsx",
    "scripts/deploy/_remote_patch_playlist_add.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Playlist add hotfix -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in UPLOADS:
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
python3 /opt/camxora/repo/scripts/deploy/_remote_patch_playlist_add.py
python3 -m py_compile /opt/camxora/repo/platform_api/services/web_music_service.py
python3 -m py_compile /opt/camxora/repo/platform_api/routers/web_music.py
grep -n 'list_playlist_memberships\|_clip_is_playable(task' /opt/camxora/repo/platform_api/services/web_music_service.py | head
grep -n 'playlists/memberships' /opt/camxora/repo/platform_api/routers/web_music.py | head
grep -n 'viewportFit\|PlaylistMembershipsProvider' /opt/camxora/repo/music_web/src/app/layout.tsx | head
chown camxora:camxora \
  /opt/camxora/repo/platform_api/services/web_music_service.py \
  /opt/camxora/repo/platform_api/routers/web_music.py \
  /opt/camxora/repo/music_web/src/components/add-to-playlist-button.tsx \
  /opt/camxora/repo/music_web/src/components/playlist-memberships-provider.tsx \
  /opt/camxora/repo/music_web/src/components/create-page-client.tsx \
  /opt/camxora/repo/music_web/src/lib/playlist-api.ts \
  /opt/camxora/repo/music_web/src/app/layout.tsx \
  /opt/camxora/repo/music_web/src/app/globals.css
systemctl restart camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 8
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
systemctl is-active camxora-api
systemctl is-active camxora-music
curl -sS -o /dev/null -w 'music=%{http_code}\n' --max-time 20 https://music.sandbox.camxora.com/create || true
echo PLAYLIST_ADD_HOTFIX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"))
        if "PLAYLIST_ADD_HOTFIX_DONE" not in out:
            raise SystemExit("Sandbox playlist-add hotfix did not finish cleanly.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
