#!/usr/bin/env python3
"""File-scoped sandbox hotfix: admin Free-tier daily credits display."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
UPLOADS = [
    (
        ROOT / "platform_api/routers/users.py",
        "/opt/camxora/repo/platform_api/routers/users.py",
    ),
    (
        ROOT / "admin_portal/src/pages/users/index.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/users/index.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/users/user-detail.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/users/user-detail.tsx",
    ),
    (
        ROOT / "admin_portal/src/types/models.ts",
        "/opt/camxora/repo/admin_portal/src/types/models.ts",
    ),
    (
        ROOT / "admin_portal/CHANGELOG.md",
        "/opt/camxora/repo/admin_portal/CHANGELOG.md",
    ),
    (
        ROOT / "platform_api/CHANGELOG.md",
        "/opt/camxora/repo/platform_api/CHANGELOG.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-18-admin-music-free-daily-display.md",
        "/opt/camxora/repo/docs/changelog/2026-08-18-admin-music-free-daily-display.md",
    ),
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Admin Free daily credits -> sandbox ({host}) ===")

    models_text = (ROOT / "admin_portal/src/types/models.ts").read_text(encoding="utf-8")
    if "WebMusicPlan" not in models_text or "music_credits_remaining?" not in models_text:
        raise SystemExit("models.ts is missing WebMusicPlan or music credit fields")

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
            print(f"Uploaded {local} -> {remote}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora \
  $REPO/platform_api/routers/users.py \
  $REPO/platform_api/CHANGELOG.md \
  $REPO/admin_portal/src/pages/users/index.tsx \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/admin_portal/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-18-admin-music-free-daily-display.md
python3 -m py_compile $REPO/platform_api/routers/users.py
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "web_music_daily_usage\|_is_music_web_user\|Free" $REPO/platform_api/routers/users.py | head
grep -n "music_credits_remaining" $REPO/admin_portal/src/pages/users/user-detail.tsx | head
echo ADMIN_MUSIC_FREE_DAILY_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
