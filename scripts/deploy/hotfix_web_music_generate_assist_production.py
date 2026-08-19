#!/usr/bin/env python3
"""File-scoped production hotfix: web-music lyric/style assist 422/502.

Uploads only allowlisted files. Does not sync a full platform_api tree.
"""

from __future__ import annotations

import sys
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
WORKTREE = Path(r"D:\Development\Projects\Electron\MusicGenerator-music-web-generate-assist")
PATCHED = REPO / ".dbg" / "prod_web_music"

SOURCES = {
    "platform_api/routers/web_music.py": PATCHED / "web_music.py",
    "platform_api/services/web_music_service.py": PATCHED / "web_music_service.py",
    "music_web/src/lib/web-music-api.ts": WORKTREE / "music_web/src/lib/web-music-api.ts",
    "music_web/src/components/create-page-client.tsx": WORKTREE
    / "music_web/src/components/create-page-client.tsx",
}


def _run(client, cmd: str, timeout: int = 300) -> tuple[int, str]:
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
    print(f"Target production host: {host}")

    missing = [rel for rel, path in SOURCES.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel, local in SOURCES.items():
            remote = f"/opt/camxora/repo/{rel}"
            parent = str(Path(remote).as_posix().rsplit("/", 1)[0])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} from {local} ...")
            sftp.put(str(local), remote)
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/music_web/src/lib/web-music-api.ts \
  $REPO/music_web/src/components/create-page-client.tsx
echo '=== verify style request ==='
grep -n "class WebMusicStyleRequest\|lyrics: str = Field\|reraise_text_assist_failure" \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/services/web_music_service.py | head -20
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
curl -sS -o /dev/null -w 'health=%{http_code}\n' --max-time 10 http://127.0.0.1:8100/health || true
API_URL=https://api.camxora.com
chown -R camxora:camxora $REPO/music_web/src/components $REPO/music_web/src/lib
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
echo WEB_MUSIC_ASSIST_HOTFIX_DONE
""",
            timeout=360,
        )
        print(out)
        print(f"exit={code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
