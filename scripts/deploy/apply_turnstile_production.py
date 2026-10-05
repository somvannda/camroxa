#!/usr/bin/env python3
"""Apply Cloudflare Turnstile keys + hostnames on production platform_api/.env."""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
DEFAULT_HOSTNAMES = "music.camxora.com,app.camxora.com,camxora.com,www.camxora.com"


def _require(secrets: dict[str, str], key: str) -> str:
    value = secrets.get(key, "").strip()
    if not value:
        raise SystemExit(f"Missing {key} in .deploy/secrets.production.env")
    return value


def _b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def main() -> int:
    # Remote output can contain non-ASCII (e.g. progress glyphs). On Windows the
    # default cp1252 console encoding would otherwise raise UnicodeEncodeError
    # *after* the remote work already succeeded, making a good deploy look failed.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild-music-web",
        action="store_true",
        help="Rebuild music_web so NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY matches API .env",
    )
    args = parser.parse_args()

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    site_key = _require(secrets, "CLOUDFLARE_TURNSTILE_SITE_KEY")
    secret_key = _require(secrets, "CLOUDFLARE_TURNSTILE_SECRET_KEY")
    hostnames = secrets.get("CLOUDFLARE_TURNSTILE_HOSTNAMES", "").strip() or DEFAULT_HOSTNAMES

    client = ssh_connect(host, user, ensure_deploy_key(), password)

    preflight = r"""
if ! grep -q cloudflare_turnstile_site_key /opt/camxora/repo/platform_api/config.py 2>/dev/null; then
  echo "ERROR: platform_api on production does not include Turnstile Settings fields yet."
  echo "Deploy platform_api from feature/web-music-credits-hardening (or merge PR #58) first."
  exit 2
fi
echo PREFLIGHT_OK
"""
    _, stdout, _ = client.exec_command(preflight, get_pty=True)
    pre_out = stdout.read().decode("utf-8", errors="replace")
    pre_code = stdout.channel.recv_exit_status()
    print(pre_out)
    if pre_code != 0:
        client.close()
        return pre_code

    remote = f"""
set -e
ENV=/opt/camxora/repo/platform_api/.env
SITE=$(printf '%s' '{_b64(site_key)}' | base64 -d)
SECRET=$(printf '%s' '{_b64(secret_key)}' | base64 -d)
HOSTNAMES=$(printf '%s' '{_b64(hostnames)}' | base64 -d)

upsert() {{
  key="$1"
  val="$2"
  if grep -q "^${{key}}=" "$ENV"; then
    sed -i "s|^${{key}}=.*|${{key}}=${{val}}|" "$ENV"
  else
    echo "${{key}}=${{val}}" >> "$ENV"
  fi
}}

upsert CLOUDFLARE_TURNSTILE_SITE_KEY "$SITE"
upsert CLOUDFLARE_TURNSTILE_SECRET_KEY "$SECRET"
upsert CLOUDFLARE_TURNSTILE_HOSTNAMES "$HOSTNAMES"

grep '^CLOUDFLARE_TURNSTILE_HOSTNAMES=' "$ENV" || true
grep '^CLOUDFLARE_TURNSTILE_SITE_KEY=' "$ENV" | cut -c1-45 || true
grep '^CLOUDFLARE_TURNSTILE_SECRET_KEY=' "$ENV" | cut -c1-25 || true

systemctl restart camxora-api
sleep 2
systemctl is-active camxora-api
echo API_TURNSTILE_APPLIED
"""

    _, stdout, stderr = client.exec_command(remote, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        client.close()
        return code

    if args.rebuild_music_web:
        rebuild = r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.camxora.com
cd $REPO/music_web
TURNSTILE_SITE=$(grep -m1 '^CLOUDFLARE_TURNSTILE_SITE_KEY=' $REPO/platform_api/.env | cut -d= -f2- || true)
if [ -z "$TURNSTILE_SITE" ]; then
  echo "ERROR: CLOUDFLARE_TURNSTILE_SITE_KEY missing after apply"
  exit 1
fi
sudo -u camxora bash -lc "
  set -e
  cd $REPO/music_web
  rm -rf .next
  npm ci || npm install --no-audit --no-fund
  cat > .env.production <<ENVEOF
NEXT_PUBLIC_API_BASE_URL=$API_URL
NEXT_PUBLIC_USER_PORTAL_URL=https://app.camxora.com
NEXT_PUBLIC_WEBSITE_URL=https://camxora.com
NEXT_PUBLIC_CAMXORA_ENV=production
NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY=$TURNSTILE_SITE
ENVEOF
  npm run build
"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music || true
echo MUSIC_WEB_REBUILD_DONE
"""
        _, stdout, stderr = client.exec_command(rebuild, get_pty=True)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        print(out)
        if err.strip():
            print(err)
        code = stdout.channel.recv_exit_status()

    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
