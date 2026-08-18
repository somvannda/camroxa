#!/usr/bin/env python3
"""File-scoped production hotfix: admin Users Tag / Music credits / Burned.

Run only when explicitly asked for production. Does not tarball-sync admin_portal.
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

USER_FIELDS = """  music_credits_remaining?: number | null;
  music_credits_limit?: number | null;
  credits_burned?: number | null;
"""
PRODUCTS_FIELD = """  /** Signup product tags, e.g. music_web, studio. */
  products?: string[];
"""

UPLOADS = [
    (
        ROOT / "admin_portal/src/pages/users/index.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/users/index.tsx",
    ),
    (
        ROOT / "admin_portal/CHANGELOG.md",
        f"{REMOTE_REPO}/admin_portal/CHANGELOG.md",
    ),
    (
        ROOT / "platform_api/CHANGELOG.md",
        f"{REMOTE_REPO}/platform_api/CHANGELOG.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-18-admin-users-product-tag.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-18-admin-users-product-tag.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-18-admin-users-music-credits.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-18-admin-users-music-credits.md",
    ),
]


def _patch_models_ts(text: str) -> str:
    if "music_credits_remaining?" not in text:
        text = text.replace(
            "  plan_name: string | null;\n  channel_profile_count: number;",
            "  plan_name: string | null;\n" + USER_FIELDS + "  channel_profile_count: number;",
            1,
        )
    if "products?: string[]" not in text:
        text = text.replace(
            "  channel_profile_count: number;\n",
            "  channel_profile_count: number;\n" + PRODUCTS_FIELD,
            1,
        )
    return text


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== Admin users Tag/Credits/Burned -> production ({host}) ===")

    local_users = ROOT / "platform_api/routers/users.py"
    if not local_users.is_file():
        raise FileNotFoundError(local_users)

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote_models = f"{REMOTE_REPO}/admin_portal/src/types/models.ts"
        with sftp.file(remote_models, "rb") as remote_file:
            models_text = remote_file.read().decode("utf-8")
        patched_models = _patch_models_ts(models_text)
        if patched_models == models_text and "products?: string[]" not in models_text:
            raise SystemExit("Could not patch production models.ts User interface")
        with sftp.file(remote_models, "wb") as remote_file:
            remote_file.write(patched_models.encode("utf-8"))
        print(f"Patched {remote_models}")

        remote_users = f"{REMOTE_REPO}/platform_api/routers/users.py"
        with sftp.file(remote_users, "rb") as remote_file:
            remote_users_text = remote_file.read().decode("utf-8")
        local_users_text = local_users.read_text(encoding="utf-8")
        remote_has_avatar = "avatar_url" in remote_users_text
        local_has_avatar = "avatar_url" in local_users_text
        if remote_has_avatar and not local_has_avatar:
            raise SystemExit(
                "Production users.py has extra fields (e.g. avatar_url). "
                "Refusing overwrite; merge enrichment into the live file first."
            )
        with sftp.file(remote_users, "wb") as remote_file:
            remote_file.write(local_users.read_bytes())
        print(f"Uploaded {remote_users}")

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
  $REPO/platform_api/CHANGELOG.md \
  $REPO/admin_portal/src/pages/users/index.tsx \
  $REPO/admin_portal/src/types/models.ts \
  $REPO/admin_portal/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-18-admin-users-product-tag.md \
  $REPO/docs/changelog/2026-08-18-admin-users-music-credits.md
python3 -m py_compile $REPO/platform_api/routers/users.py
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8000/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "header: 'Burned'" $REPO/admin_portal/src/pages/users/index.tsx
grep -n "web_subscriptions" $REPO/platform_api/routers/users.py | head
echo ADMIN_USERS_PRODUCT_TAG_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out + "\n")
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "ADMIN_USERS_PRODUCT_TAG_PRODUCTION_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
