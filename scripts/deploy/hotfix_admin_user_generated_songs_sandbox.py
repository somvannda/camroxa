#!/usr/bin/env python3
"""File-scoped sandbox hotfix: admin user generated-songs browser."""

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
        ROOT / "platform_api/routers/admin_user_web_music.py",
        "/opt/camxora/repo/platform_api/routers/admin_user_web_music.py",
    ),
    (
        ROOT / "admin_portal/src/pages/users/user-generated-songs.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/users/user-generated-songs.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/users/user-detail.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/users/user-detail.tsx",
    ),
    (
        ROOT / "admin_portal/src/hooks/use-users.ts",
        "/opt/camxora/repo/admin_portal/src/hooks/use-users.ts",
    ),
    (
        ROOT / "admin_portal/src/types/models.ts",
        "/opt/camxora/repo/admin_portal/src/types/models.ts",
    ),
    (
        ROOT / "docs/changelog/2026-08-19-admin-user-generated-songs.md",
        "/opt/camxora/repo/docs/changelog/2026-08-19-admin-user-generated-songs.md",
    ),
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Admin user generated songs -> sandbox ({host}) ===")

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
python3 - <<'PY'
from pathlib import Path
path = Path("/opt/camxora/repo/platform_api/routers/users.py")
text = path.read_text(encoding="utf-8")
needle = "from platform_api.routers.admin_user_web_music import router as admin_web_music_router"
if needle not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + needle + "\nrouter.include_router(admin_web_music_router)\n"
    path.write_text(text, encoding="utf-8")
    print("Patched users.py to include admin_web_music_router")
else:
    print("users.py already includes admin_web_music_router")
PY
chown -R camxora:camxora \
  $REPO/platform_api/routers/admin_user_web_music.py \
  $REPO/platform_api/routers/users.py \
  $REPO/admin_portal/src/pages/users/user-generated-songs.tsx \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/admin_portal/src/hooks/use-users.ts \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/docs/changelog/2026-08-19-admin-user-generated-songs.md
python3 -m py_compile $REPO/platform_api/routers/admin_user_web_music.py $REPO/platform_api/routers/users.py
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/sbx_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "admin_web_music_router\|web-music/generations" $REPO/platform_api/routers/users.py $REPO/platform_api/routers/admin_user_web_music.py | head
grep -n "UserGeneratedSongs" $REPO/admin_portal/src/pages/users/user-detail.tsx | head
echo ADMIN_USER_GENERATED_SONGS_DONE
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
