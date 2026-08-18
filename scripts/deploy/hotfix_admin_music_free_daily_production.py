#!/usr/bin/env python3
"""File-scoped production hotfix: admin Free-tier daily credits display.

Patches live production files in place. Does not tarball-sync platform_api.
Run only when explicitly asked for production.
"""

from __future__ import annotations

import sys
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
REMOTE_REPO = "/opt/camxora/repo"
DBG = ROOT / ".dbg" / "prod_admin_free_daily"

UPLOADS = [
    (DBG / "users.py", f"{REMOTE_REPO}/platform_api/routers/users.py"),
    (DBG / "models.ts", f"{REMOTE_REPO}/admin_portal/src/types/models.ts"),
    (DBG / "user-detail.tsx", f"{REMOTE_REPO}/admin_portal/src/pages/users/user-detail.tsx"),
    (
        ROOT / "docs/changelog/2026-08-18-admin-music-free-daily-display.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-18-admin-music-free-daily-display.md",
    ),
]


def _validate() -> None:
    users = (DBG / "users.py").read_text(encoding="utf-8")
    models = (DBG / "models.ts").read_text(encoding="utf-8")
    detail = (DBG / "user-detail.tsx").read_text(encoding="utf-8")
    if "avatar_url" not in users:
        raise SystemExit("Patched production users.py is missing avatar_url")
    if "web_subscriptions" not in users or "_is_music_web_user" not in users:
        raise SystemExit("Patched production users.py is missing Music credit helpers")
    if "web_music_daily_usage" not in users:
        raise SystemExit("Patched production users.py is missing daily usage query")
    if "WebMusicPlan" not in models:
        raise SystemExit("Patched production models.ts is missing WebMusicPlan")
    if "music_credits_remaining?" not in models:
        raise SystemExit("Patched production models.ts is missing music credit fields")
    if "music_credits_remaining" not in detail:
        raise SystemExit("Patched production user-detail.tsx is missing remaining/limit")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    _validate()
    print(f"=== Admin Free daily credits -> production ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, remote in UPLOADS:
            if not local.is_file():
                raise FileNotFoundError(local)
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora \
  $REPO/platform_api/routers/users.py \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/docs/changelog/2026-08-18-admin-music-free-daily-display.md
python3 -m py_compile $REPO/platform_api/routers/users.py
grep -n "avatar_url\|_is_music_web_user\|web_music_daily_usage" $REPO/platform_api/routers/users.py | head
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "music_credits_remaining" $REPO/admin_portal/src/pages/users/user-detail.tsx | head
echo ADMIN_MUSIC_FREE_DAILY_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out + "\n")
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "ADMIN_MUSIC_FREE_DAILY_PRODUCTION_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
