#!/usr/bin/env python3
"""Production-only UI copy hotfix: monthly free-pool wording.

Uploads monthly-aware copy for the free allowance to 82.197.71.248:
- admin_portal: "Camxora Music — Free monthly pool" card
- music_web: logged-in credit balance/header + upgrade CTA + public pricing copy

Backs up originals, rebuilds admin_portal and music_web on the server, restarts
camxora-music, verifies. Restores backups if either build fails.
NO git commit / merge. Run only when explicitly asked for production.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
DBG = ROOT / ".dbg" / "prod-ui-monthly"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
REMOTE_REPO = "/opt/camxora/repo"
STAMP = time.strftime("%Y%m%d-%H%M%S")

UPLOADS = [
    (
        DBG / "admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
        "admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
    ),
    (
        DBG / "music_web/src/components/credit-balance-card.tsx",
        "music_web/src/components/credit-balance-card.tsx",
    ),
    (
        DBG / "music_web/src/components/credit-header.tsx",
        "music_web/src/components/credit-header.tsx",
    ),
    (
        DBG / "music_web/src/components/create-page-client.tsx",
        "music_web/src/components/create-page-client.tsx",
    ),
    (
        DBG / "music_web/src/components/pricing-plans-section.tsx",
        "music_web/src/components/pricing-plans-section.tsx",
    ),
    (
        DBG / "music_web/src/components/pricing-modal.tsx",
        "music_web/src/components/pricing-modal.tsx",
    ),
    (
        DBG / "music_web/src/components/pricing-page-client.tsx",
        "music_web/src/components/pricing-page-client.tsx",
    ),
]

REMOTE_CMD = r'''
set -e
REPO=/opt/camxora/repo
STAMP="%STAMP%"

echo "--- backup originals ---"
for f in \
  admin_portal/src/pages/plans/music-web-free-credits-section.tsx \
  music_web/src/components/credit-balance-card.tsx \
  music_web/src/components/credit-header.tsx \
  music_web/src/components/create-page-client.tsx \
  music_web/src/components/pricing-plans-section.tsx \
  music_web/src/components/pricing-modal.tsx \
  music_web/src/components/pricing-page-client.tsx; do
  cp -p $REPO/$f $REPO/$f.pre-monthly-ui-$STAMP.bak
done
chown -R camxora:camxora \
  $REPO/admin_portal/src/pages/plans/music-web-free-credits-section.tsx \
  $REPO/music_web/src/components

restore() {
  echo "RESTORING BACKUPS"
  for f in \
    admin_portal/src/pages/plans/music-web-free-credits-section.tsx \
    music_web/src/components/credit-balance-card.tsx \
    music_web/src/components/credit-header.tsx \
    music_web/src/components/create-page-client.tsx \
    music_web/src/components/pricing-plans-section.tsx \
    music_web/src/components/pricing-modal.tsx \
    music_web/src/components/pricing-page-client.tsx; do
    cp -p $REPO/$f.pre-monthly-ui-$STAMP.bak $REPO/$f
  done
  exit 3
}

echo "--- build admin_portal ---"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build' || restore
echo "--- build music_web ---"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build' || restore

echo "--- restart music service ---"
systemctl restart camxora-music
sleep 4
systemctl is-active camxora-music
echo "--- smoke ---"
curl -s -o /dev/null -w "music http=%{http_code}\n" http://127.0.0.1:3102/ || echo MUSIC_HTTP_FAIL
echo "--- built copy markers ---"
grep -rl "Free monthly pool" $REPO/admin_portal/dist 2>/dev/null | head -3 || echo "NO_ADMIN_MARKER"
grep -rl "free songs every month" $REPO/music_web/.next/static 2>/dev/null | head -3 || echo "NO_MUSIC_MARKER"
journalctl -u camxora-music --since "2 minutes ago" --no-pager 2>/dev/null | grep -iE "Traceback|ERROR|Failed to compile" | tail -5 || true
echo APPLY_MUSIC_WEB_FREE_MONTHLY_UI_PRODUCTION_DONE
'''


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    for local, _rel in UPLOADS:
        if not local.is_file():
            raise FileNotFoundError(local)

    print(f"=== Apply monthly UI copy -> production ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, rel in UPLOADS:
            remote = f"{REMOTE_REPO}/{rel}"
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()

        cmd = REMOTE_CMD.replace("%STAMP%", STAMP)
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=1200)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out + "\n")
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "APPLY_MUSIC_WEB_FREE_MONTHLY_UI_PRODUCTION_DONE" not in out:
            print("Apply did not finish cleanly (see output above).")
            return 1
        print("Apply completed.")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
