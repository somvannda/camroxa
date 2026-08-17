#!/usr/bin/env python3
"""File-scoped production hotfix: music-web audio proxy + catalog URL hiding.

Uploads allowlisted files only. Does not sync a full platform_api tree.
Does not run `alembic upgrade heads`.
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

FILES = [
    "platform_api/services/audio_origin_proxy.py",
    "platform_api/services/streaming_catalog_service.py",
    "platform_api/services/web_music_service.py",
    "platform_api/services/suno_audio_resolver.py",
    "platform_api/routers/web_music.py",
    "platform_api/routers/streaming_public.py",
    "platform_api/routers/callbacks.py",
    "platform_api/routers/auth.py",
    "platform_api/repositories/batch_repo.py",
    "platform_api/migrations/runner.py",
    "music_web/src/lib/streaming-api.ts",
    "music_web/src/lib/web-music-api.ts",
    "music_web/src/components/create-page-client.tsx",
    "music_web/src/components/player-provider.tsx",
]


def _run(client, cmd: str, timeout: int = 420) -> tuple[int, str]:
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
    print(f"Target production host: {host}", flush=True)

    missing = [rel for rel in FILES if not (ROOT / rel).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {missing}")

    nginx_conf = DEPLOY / "nginx-camxora-production.conf"
    if not nginx_conf.is_file():
        raise SystemExit(f"Missing nginx config: {nginx_conf}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            remote = f"/opt/camxora/repo/{rel}"
            parent = str(Path(remote).as_posix().rsplit("/", 1)[0])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel} ...", flush=True)
            sftp.put(str(ROOT / rel), remote)
        print("Uploading nginx-camxora-production.conf ...", flush=True)
        sftp.put(str(nginx_conf), "/tmp/nginx-camxora-production.conf")
        sftp.close()

        code, out = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/audio_origin_proxy.py \
  $REPO/platform_api/services/streaming_catalog_service.py \
  $REPO/platform_api/services/web_music_service.py \
  $REPO/platform_api/services/suno_audio_resolver.py \
  $REPO/platform_api/routers/web_music.py \
  $REPO/platform_api/routers/streaming_public.py \
  $REPO/platform_api/routers/callbacks.py \
  $REPO/platform_api/routers/auth.py \
  $REPO/platform_api/repositories/batch_repo.py \
  $REPO/platform_api/migrations/runner.py \
  $REPO/music_web/src/lib/streaming-api.ts \
  $REPO/music_web/src/lib/web-music-api.ts \
  $REPO/music_web/src/components/create-page-client.tsx \
  $REPO/music_web/src/components/player-provider.tsx

echo '=== duration columns ==='
sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 -c "
ALTER TABLE suno_tasks
  ADD COLUMN IF NOT EXISTS duration_ok DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS duration_alt DOUBLE PRECISION;
"

echo '=== quarantine broken alembic stubs ==='
python3 - <<'PY'
from pathlib import Path
import shutil
vers = Path("/opt/camxora/repo/platform_api/migrations/versions")
qdir = Path("/tmp/alembic-broken-stubs-20260817")
qdir.mkdir(parents=True, exist_ok=True)
needles = (
    "084_provider_balance_events",
    "e5077c52f2b7",
    "fffddbe8fbb3",
    "ff781163cfbb",
    "1f0ad008d202",
)
moved = []
for path in sorted(vers.glob("*.py")):
    if path.name.startswith("103_"):
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if any(needle in text for needle in needles):
        shutil.move(str(path), str(qdir / path.name))
        moved.append(path.name)
print("MOVED", ", ".join(moved) if moved else "NONE")
PY
find $REPO/platform_api/migrations -name '__pycache__' -type d -exec rm -rf {} + || true

echo '=== nginx ==='
cp /tmp/nginx-camxora-production.conf /etc/nginx/sites-available/camxora-production
ln -sf /etc/nginx/sites-available/camxora-production /etc/nginx/sites-enabled/camxora-production
nginx -t
systemctl reload nginx

echo '=== restart api ==='
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 2
done
echo HEALTH_BODY
cat /tmp/prod_health.json || true
echo
test "$code" = "200"

echo '=== rebuild music_web ==='
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
echo MUSIC_WEB_PLAYBACK_PROXY_PROD_DONE
""",
            timeout=480,
        )
        print(out.encode("ascii", errors="replace").decode("ascii"))
        print(f"exit={code}", flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
