#!/usr/bin/env python3
"""File-scoped production hotfix: album tracklist Time-column alignment.

Uploads only allowlisted music_web files from origin/main, then rebuilds
camxora-music. Does not sync a mixed local music_web tree.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(SCRIPT_DIR))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REPO = SCRIPT_DIR.parents[1]
FILES = [
    "music_web/src/components/album-hero.tsx",
    "music_web/src/components/album-playback-controls.tsx",
    "music_web/src/components/album-track-list.tsx",
    "music_web/src/components/track-row.tsx",
]


def _git_show(rel: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"origin/main:{rel}"],
    )


def _run(client, cmd: str, timeout: int = 300) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = out + ("\n" + err if err.strip() else "")
    return code, text.encode("ascii", errors="replace").decode("ascii")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")
    print("File source: origin/main")

    tmp = Path(tempfile.mkdtemp(prefix="album-ux-prod-"))
    for rel in FILES:
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_git_show(rel))
        print(f"  packed {rel}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            parent = str(Path(remote).parent).replace("\\", "/")
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...")
            sftp.put(str(tmp / rel), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.camxora.com
chown -R camxora:camxora $REPO/music_web/src/components
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  TURNSTILE_SITE=\$(grep -m1 '^CLOUDFLARE_TURNSTILE_SITE_KEY=' $REPO/platform_api/.env | cut -d= -f2- || true)
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://camxora.com
NEXT_PUBLIC_CAMXORA_ENV=production
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=\$TURNSTILE_SITE
ENVEOF
  npm run build
"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo MUSIC_WEB_ALBUM_UX_HOTFIX_DONE
""",
            timeout=300,
        )
        print(out)
        print(f"exit={code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
