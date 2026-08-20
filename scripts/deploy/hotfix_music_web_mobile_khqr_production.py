#!/usr/bin/env python3
"""File-scoped production hotfix: music-web mobile UI + CutLuy KHQR.

Uploads allowlisted files from origin/main, restarts camxora-api, and rebuilds
camxora-music. Does not sync a mixed local platform_api or music_web tree.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / ".venv" / "Lib" / "site-packages"))
PRIMARY = Path(r"D:\Development\Projects\Electron\MusicGenerator")
for candidate in (PRIMARY / "scripts" / "deploy", SCRIPT_DIR):
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
REPO = SCRIPT_DIR.parents[1]
API_FILES = [
    "platform_api/services/shared/cutluy_service.py",
    "platform_api/services/v2/subscription_service.py",
    "platform_api/services/v2/topup_service.py",
    "platform_api/routers/v2_subscriptions.py",
    "platform_api/routers/v2_topups.py",
]
MUSIC_WEB_FILES = [
    "music_web/package.json",
    "music_web/package-lock.json",
    "music_web/src/app/globals.css",
    "music_web/src/app/layout.tsx",
    "music_web/src/components/brand-lockup.tsx",
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/cutluy-checkout-modal.tsx",
    "music_web/src/components/khqr-code.tsx",
    "music_web/src/components/music-form-ui.tsx",
    "music_web/src/components/player-bar.tsx",
    "music_web/src/components/playlist-detail-page-client.tsx",
    "music_web/src/components/playlists-page-client.tsx",
    "music_web/src/components/pricing-modal.tsx",
    "music_web/src/components/pricing-page-client.tsx",
    "music_web/src/components/shell-switcher.tsx",
    "music_web/src/components/sidebar.tsx",
    "music_web/src/components/site-header.tsx",
    "music_web/src/components/subscription-section.tsx",
    "music_web/src/components/topup-modal.tsx",
    "music_web/src/components/user-menu.tsx",
    "music_web/src/lib/subscription-api.ts",
    "music_web/src/lib/use-mobile-keyboard-inset.ts",
]
FILES = API_FILES + MUSIC_WEB_FILES


def _git_show(rel: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "show", f"origin/main:{rel}"],
    )


def _run(client, cmd: str, timeout: int = 600) -> tuple[int, str]:
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

    tmp = Path(tempfile.mkdtemp(prefix="mobile-khqr-prod-"))
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
chown camxora:camxora \
  $REPO/platform_api/services/shared/cutluy_service.py \
  $REPO/platform_api/services/v2/subscription_service.py \
  $REPO/platform_api/services/v2/topup_service.py \
  $REPO/platform_api/routers/v2_subscriptions.py \
  $REPO/platform_api/routers/v2_topups.py
chown -R camxora:camxora $REPO/music_web/src $REPO/music_web/package.json $REPO/music_web/package-lock.json
echo '=== restart api ==='
systemctl restart camxora-api
health=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  health=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$health
  if [ "$health" = "200" ]; then
    break
  fi
  sleep 2
done
test "$health" = "200"
grep -n 'qr_string' $REPO/platform_api/services/v2/subscription_service.py | head -5
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
echo MUSIC_WEB_MOBILE_KHQR_PROD_DONE
""",
            timeout=600,
        )
        print(out)
        print(f"exit={code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
