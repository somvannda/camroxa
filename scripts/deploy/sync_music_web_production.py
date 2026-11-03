#!/usr/bin/env python3
"""Sync music_web source to production and rebuild — from one commit of main.

Packages ``origin/main`` (not the working tree), verifies the manifest on the
server before rebuilding, and prunes files the previous deploy shipped that
this one does not.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    build_source_bundle,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
    upload_verifier,
)
from deploy_guards import (  # noqa: E402
    acquire_remote_lock,
    enforce_deploy_gate,
    post_deploy_record,
    release_remote_lock,
)
from release_source import DEFAULT_SOURCE_REF, SOURCE_MODE_ENV  # noqa: E402

# Remote output may contain non-ASCII; a Windows cp1252 console would otherwise
# raise UnicodeEncodeError after the remote work already succeeded.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRODUCTION_HOST = "82.197.71.248"


def _run(client, cmd: str) -> int:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err)
    return stdout.channel.recv_exit_status()


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    bundle = build_source_bundle(DEFAULT_SOURCE_REF)
    mode = os.environ.get(SOURCE_MODE_ENV, "commit").strip().lower()
    gate = enforce_deploy_gate(
        commit=bundle.commit,
        require_merged=True,
        require_clean=(mode == "worktree"),
    )

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    lock = acquire_remote_lock(client)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
            remote_file.write(bundle.path.read_bytes())
        sftp.close()
        upload_verifier(client)

        code = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
API_URL=https://api.camxora.com
cp -f "$REPO/.deploy-manifest.json" "$REPO/.deploy-manifest.prev.json" 2>/dev/null || true
tar -xzf /tmp/camxora-src.tar.gz -C $REPO music_web .deploy-manifest.json
python3 /tmp/camxora-verify-manifest.py \
  --repo $REPO \
  --manifest $REPO/.deploy-manifest.json \
  --scope music_web \
  --prev-manifest $REPO/.deploy-manifest.prev.json
rm -f $REPO/.deploy-manifest.prev.json
chown -R camxora:camxora $REPO/music_web
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
echo MUSIC_WEB_PRODUCTION_SYNC_DONE
""",
        )
        if code == 0:
            post_deploy_record(
                client,
                gate,
                target="production",
                script=Path(__file__).name,
                extra={
                    "source_commit": bundle.commit,
                    "source_ref": bundle.ref,
                    "source_mode": bundle.mode,
                    "source_files": bundle.files,
                    "manifest": ".deploy-manifest.json",
                    "scope": "music_web",
                },
            )
    finally:
        release_remote_lock(client, lock)
        client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
