#!/usr/bin/env python3
"""File-scoped sandbox hotfix: admin Users lifetime Music burn display."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
SIBLING_DEPLOY = ROOT.parent / "MusicGenerator" / "scripts" / "deploy"
for candidate in (DEPLOY, SIBLING_DEPLOY):
    venv = candidate / ".venv" / "Lib" / "site-packages"
    if venv.is_dir():
        sys.path.insert(0, str(venv))
        sys.path.insert(0, str(candidate))
        break

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
DBG = ROOT / ".dbg" / "sandbox_admin_users_credits"
UPLOADS = [
    (
        DBG / "users.py",
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
        ROOT / "docs/changelog/2026-08-19-admin-users-lifetime-burn.md",
        "/opt/camxora/repo/docs/changelog/2026-08-19-admin-users-lifetime-burn.md",
    ),
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")

    users = (DBG / "users.py").read_text(encoding="utf-8")
    index = (ROOT / "admin_portal/src/pages/users/index.tsx").read_text(encoding="utf-8")
    if "avatar_url" not in users:
        raise SystemExit("Patched sandbox users.py is missing avatar_url")
    if "lifetime_used" not in users or "_studio_credits_burned" not in users:
        raise SystemExit("Patched sandbox users.py is missing lifetime burn helpers")
    if "usedToday" not in index:
        raise SystemExit("Local Users table is still using credits_burned as today's used")

    print(f"=== Admin lifetime burn -> sandbox ({host}) ===")
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
  $REPO/admin_portal/src/pages/users/index.tsx \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/docs/changelog/2026-08-19-admin-users-lifetime-burn.md
python3 -m py_compile $REPO/platform_api/routers/users.py
grep -n "lifetime_used\|_studio_credits_burned\|_is_music_web_user" $REPO/platform_api/routers/users.py | head
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -sS -m 3 -o /tmp/sb_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
echo ADMIN_LIFETIME_BURN_SANDBOX_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write((out + "\n").encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "ADMIN_LIFETIME_BURN_SANDBOX_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
