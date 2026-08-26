"""File-scoped production music_web player split.

Uploads only player modules + player-provider. Does not touch platform_api,
does not restart camxora-api, and does not extract a full music_web tarball
(that would overlay /api/v3 client paths onto production, which has no v3).
"""

from __future__ import annotations

import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = CODE_ROOT.parent / "MusicGenerator"
if not (HOST_REPO / ".deploy" / "secrets.production.env").is_file():
    HOST_REPO = CODE_ROOT
DEPLOY = HOST_REPO / "scripts" / "deploy"
for candidate in (DEPLOY / ".venv" / "Lib" / "site-packages",):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

PLAYERS_ROOT = CODE_ROOT / "music_web" / "src" / "lib" / "players"


def player_files() -> list[str]:
    files = ["music_web/src/components/player-provider.tsx"]
    for path in sorted(PLAYERS_ROOT.rglob("*")):
        if path.is_file() and path.suffix in {".ts", ".tsx"}:
            files.append(path.relative_to(CODE_ROOT).as_posix())
    return files


def main() -> int:
    files = player_files()
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")
    print(f"Uploading {len(files)} music_web player files (API untouched)")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in files:
            local = CODE_ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel}"
            parent = remote.rsplit("/", 1)[0]
            _, stdout, _ = client.exec_command(f"mkdir -p {parent}")
            stdout.channel.recv_exit_status()
            print(f"Uploading {rel}", flush=True)
            sftp.put(str(local), remote)
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora $REPO/music_web/src/lib/players $REPO/music_web/src/components/player-provider.tsx
test -f $REPO/music_web/src/lib/players/ios-chrome.ts
test -f $REPO/music_web/src/lib/players/win-chrome.ts
grep -q 'getPlayBackend' $REPO/music_web/src/components/player-provider.tsx
grep -q '/api/v1/web-music/licenses/play' $REPO/music_web/src/lib/players/engines/html-native.ts
# Do not restart API. Production has no v3.
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-music
echo music_http=$(curl -sS -o /dev/null -w '%{http_code}' -H 'CF-IPCountry: KH' https://music.camxora.com/)
echo PLAYER_SPLIT_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            print(err)
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
