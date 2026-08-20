#!/usr/bin/env python3
"""File-scoped production deploy: protected playback.

Allowlisted paths only. Does not tar the full platform_api or admin trees.
Host must be 82.197.71.248. Does not backfill B2 objects.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

API_FILES = [
    "platform_api/config.py",
    "platform_api/main.py",
    "platform_api/wire_dependencies.py",
    "platform_api/middleware/auth.py",
    "platform_api/routers/web_music.py",
    "platform_api/routers/web_music_licenses.py",
    "platform_api/routers/streaming_public.py",
    "platform_api/routers/streaming_admin.py",
    "platform_api/routers/admin_user_web_music.py",
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/audio_packager.py",
    "platform_api/services/audio_package_service.py",
    "platform_api/services/content_license_service.py",
    "platform_api/services/forensic_watermark.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/streaming_catalog_service.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/services/batch_service.py",
    "platform_api/migrations/versions/107_protected_playback.py",
]

MUSIC_WEB_FILES = [
    "music_web/src/lib/camxora-decrypt.ts",
    "music_web/src/lib/content-license.ts",
    "music_web/src/lib/streaming-api.ts",
    "music_web/src/lib/web-music-api.ts",
    "music_web/src/lib/playlist-api.ts",
    "music_web/src/components/player-provider.tsx",
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/home-gate.tsx",
    "music_web/src/components/playlist-detail-page-client.tsx",
]

ADMIN_FILES = [
    "admin_portal/src/hooks/use-playback-audit.ts",
    "admin_portal/src/pages/streaming/playback-audit.tsx",
    "admin_portal/src/pages/streaming/catalog.tsx",
    "admin_portal/src/hooks/use-streaming.ts",
    "admin_portal/src/App.tsx",
    "admin_portal/src/components/layout/sidebar.tsx",
]


def _run(client, cmd: str, timeout: int = 600) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def _upload(client, sftp, rels: list[str]) -> None:
    for rel in rels:
        local = ROOT / rel
        if not local.is_file():
            raise SystemExit(f"Missing source file: {rel}")
        remote = f"/opt/camxora/repo/{rel}".replace("\\", "/")
        parent = remote.rsplit("/", 1)[0]
        _, stdout, _ = client.exec_command(f"mkdir -p {parent}")
        stdout.channel.recv_exit_status()
        print(f"Uploading {rel}", flush=True)
        sftp.put(str(local), remote)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}", flush=True)

    nginx_conf = DEPLOY / "nginx-camxora-production.conf"
    if not nginx_conf.is_file():
        raise SystemExit(f"Missing nginx config: {nginx_conf}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        code, out = _run(
            client,
            r"""
set -e
echo HOST=$(hostname -I | awk '{print $1}')
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
""",
        )
        print(out, flush=True)
        if code != 0:
            return code
        if "107_protected_playback" not in out and "106_web_music_stream_ready" not in out:
            print("REFUSE: production alembic head is not 106 or 107")
            return 2

        sftp = client.open_sftp()
        print("=== 1. API files ===", flush=True)
        _upload(client, sftp, API_FILES)
        print("=== nginx conf ===", flush=True)
        sftp.put(str(nginx_conf), "/tmp/nginx-camxora-production.conf")
        print("=== 4. music_web files ===", flush=True)
        _upload(client, sftp, MUSIC_WEB_FILES)
        print("=== 5. admin files ===", flush=True)
        _upload(client, sftp, ADMIN_FILES)
        sftp.close()

        api_chown = " ".join(f"/opt/camxora/repo/{p}" for p in API_FILES)
        mw_chown = " ".join(f"/opt/camxora/repo/{p}" for p in MUSIC_WEB_FILES)
        ad_chown = " ".join(f"/opt/camxora/repo/{p}" for p in ADMIN_FILES)

        print("=== 2. alembic + API restart ===", flush=True)
        code, out = _run(
            client,
            rf"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora {api_chown}
test -f $REPO/platform_api/migrations/versions/107_protected_playback.py
sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && source .venv/bin/activate && alembic upgrade head'
sudo -u postgres psql -d camxora_platform -t -A -c "SELECT version_num FROM alembic_version;"
grep -E '^PLATFORM_(CONTENT_AUDIO_KEK|ENCRYPTION_MASTER_KEY)=' $REPO/platform_api/.env | cut -d= -f1 || true
systemctl restart camxora-api
systemctl list-units --type=service --all --no-pager --plain 'camxora-worker*' \
  | awk '{{print $1}}' \
  | grep -E '^camxora-worker' \
  | while read -r unit; do systemctl restart "$unit" || true; done
code=""
for i in 1 2 3 4 5 6 7 8 9 10 12 14 16 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{{http_code}}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/prod_health.json || true
echo
test "$code" = "200"
curl -sS -m 8 http://127.0.0.1:8100/api/v1/web-music/licenses/module-hash
echo
echo API_STAGE_DONE
""",
            timeout=180,
        )
        print(out, flush=True)
        if code != 0:
            return code

        print("=== 3. nginx ===", flush=True)
        code, out = _run(
            client,
            r"""
set -e
cp /tmp/nginx-camxora-production.conf /etc/nginx/sites-available/camxora-production
ln -sf /etc/nginx/sites-available/camxora-production /etc/nginx/sites-enabled/camxora-production
nginx -t
systemctl reload nginx
grep -n 'web-music/licenses' /etc/nginx/sites-available/camxora-production | head
echo NGINX_APPLIED_PRODUCTION
""",
        )
        print(out, flush=True)
        if code != 0:
            return code

        print("=== 4. rebuild music_web ===", flush=True)
        code, out = _run(
            client,
            rf"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora {mw_chown}
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo MUSIC_WEB_PRODUCTION_DONE
""",
            timeout=300,
        )
        print(out[-8000:] if len(out) > 8000 else out, flush=True)
        if code != 0:
            return code

        print("=== 5. rebuild admin ===", flush=True)
        code, out = _run(
            client,
            rf"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora {ad_chown}
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
echo ADMIN_PRODUCTION_DONE
""",
            timeout=300,
        )
        print(out[-8000:] if len(out) > 8000 else out, flush=True)
        if code != 0:
            return code

        print("=== smoke ===", flush=True)
        code, out = _run(
            client,
            r"""
set -e
echo module_hash=$(curl -sS -m 8 http://127.0.0.1:8100/api/v1/web-music/licenses/module-hash)
echo music_http=$(curl -sS -o /dev/null -w '%{http_code}' -H 'CF-IPCountry: KH' https://music.camxora.com/)
echo admin_http=$(curl -sS -o /dev/null -w '%{http_code}' https://admin.camxora.com/)
echo openapi_licenses
curl -sS -m 20 http://127.0.0.1:8100/api/v1/openapi.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(p for p in d.get("paths",{}) if "web-music/licenses" in p) or "NO_LICENSE_PATHS")'
echo PROD_PROTECTED_PLAYBACK_DONE
""",
        )
        print(out, flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
