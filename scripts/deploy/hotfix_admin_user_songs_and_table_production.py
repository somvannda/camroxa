#!/usr/bin/env python3
"""File-scoped production hotfix: generated songs + Users Tag/Free/used-total.

Does not tarball-sync platform_api or admin_portal. Run only when production
is explicitly requested.
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
UPLOADS = [
    (
        ROOT / "platform_api/routers/users.py",
        f"{REMOTE_REPO}/platform_api/routers/users.py",
    ),
    (
        ROOT / "platform_api/routers/admin_user_web_music.py",
        f"{REMOTE_REPO}/platform_api/routers/admin_user_web_music.py",
    ),
    (
        ROOT / "admin_portal/src/pages/users/index.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/users/index.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/users/user-detail.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/users/user-detail.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/users/user-generated-songs.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/users/user-generated-songs.tsx",
    ),
    (
        ROOT / "admin_portal/src/hooks/use-users.ts",
        f"{REMOTE_REPO}/admin_portal/src/hooks/use-users.ts",
    ),
    (
        ROOT / "admin_portal/src/types/models.ts",
        f"{REMOTE_REPO}/admin_portal/src/types/models.ts",
    ),
    (
        ROOT / "docs/changelog/2026-08-19-admin-user-generated-songs.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-19-admin-user-generated-songs.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-19-sandbox-admin-users-table-sync.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-19-sandbox-admin-users-table-sync.md",
    ),
]


def _require(path: Path, *needles: str) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [item for item in needles if item not in text]
    if missing:
        raise SystemExit(f"{path} missing required markers: {missing}")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    _require(
        ROOT / "platform_api/routers/users.py",
        "_is_music_web_user",
        "avatar_url",
        "admin_web_music_router",
        "generation_frozen",
        "web_music_daily_usage",
        "upload_path_exists",
    )
    _require(
        ROOT / "admin_portal/src/pages/users/index.tsx",
        "header: 'Tag'",
        "header: 'Burned'",
        "music_credits_limit",
    )
    _require(
        ROOT / "admin_portal/src/pages/users/user-detail.tsx",
        "UserGeneratedSongs",
        "useFreezeGeneration",
        "music_credits_limit",
    )
    _require(
        ROOT / "admin_portal/src/hooks/use-users.ts",
        "useFreezeGeneration",
        "useUserWebMusicWorkspaces",
    )
    _require(
        ROOT / "admin_portal/src/types/models.ts",
        "WebMusicPlan",
        "music_credits_remaining?",
        "generation_frozen?",
    )

    print(f"=== Admin generated songs + Users table -> production ({host}) ===")

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
  $REPO/platform_api/routers/admin_user_web_music.py \
  $REPO/admin_portal/src/pages/users/index.tsx \
  $REPO/admin_portal/src/pages/users/user-detail.tsx \
  $REPO/admin_portal/src/pages/users/user-generated-songs.tsx \
  $REPO/admin_portal/src/hooks/use-users.ts \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/docs/changelog/2026-08-19-admin-user-generated-songs.md \
  $REPO/docs/changelog/2026-08-19-sandbox-admin-users-table-sync.md
python3 -m py_compile $REPO/platform_api/routers/users.py $REPO/platform_api/routers/admin_user_web_music.py
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "_is_music_web_user\|admin_web_music_router\|avatar_url\|generation_frozen" $REPO/platform_api/routers/users.py | head
grep -n "header: 'Tag'\|header: 'Burned'" $REPO/admin_portal/src/pages/users/index.tsx | head
grep -n "UserGeneratedSongs\|useFreezeGeneration" $REPO/admin_portal/src/pages/users/user-detail.tsx | head
echo ADMIN_USER_SONGS_AND_TABLE_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace") + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "ADMIN_USER_SONGS_AND_TABLE_PRODUCTION_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
