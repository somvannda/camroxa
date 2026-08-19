#!/usr/bin/env python3
"""File-scoped production hotfix: admin Music Web free daily credits setting.

Patches live production admin files in place. Does not tarball-sync the tree.
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
UPLOADS = [
    (
        ROOT / "admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/plans/index.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/plans/index.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/settings/index.tsx",
        f"{REMOTE_REPO}/admin_portal/src/pages/settings/index.tsx",
    ),
    (
        ROOT / "admin_portal/CHANGELOG.md",
        f"{REMOTE_REPO}/admin_portal/CHANGELOG.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md",
        f"{REMOTE_REPO}/docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md",
    ),
]


def _validate() -> None:
    section = (
        ROOT / "admin_portal/src/pages/plans/music-web-free-credits-section.tsx"
    ).read_text(encoding="utf-8")
    plans = (ROOT / "admin_portal/src/pages/plans/index.tsx").read_text(encoding="utf-8")
    settings = (ROOT / "admin_portal/src/pages/settings/index.tsx").read_text(encoding="utf-8")
    if "web_music_free_daily_credits" not in section:
        raise SystemExit("music-web-free-credits-section.tsx is missing the setting key")
    if "MusicWebFreeCreditsSection" not in plans:
        raise SystemExit("plans/index.tsx is missing MusicWebFreeCreditsSection")
    if "music-web" not in settings or "MusicWebFreeCreditsSection" not in settings:
        raise SystemExit("settings/index.tsx is missing the Music Web tab")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    _validate()
    print(f"=== Admin Music Web free daily credits -> production ({host}) ===")

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
  $REPO/admin_portal/src/pages/plans/music-web-free-credits-section.tsx \
  $REPO/admin_portal/src/pages/plans/index.tsx \
  $REPO/admin_portal/src/pages/settings/index.tsx \
  $REPO/admin_portal/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "MusicWebFreeCreditsSection\|web_music_free_daily_credits" \
  $REPO/admin_portal/src/pages/plans/index.tsx \
  $REPO/admin_portal/src/pages/settings/index.tsx \
  $REPO/admin_portal/src/pages/plans/music-web-free-credits-section.tsx | head
echo ADMIN_MUSIC_FREE_DAILY_CREDITS_SETTING_PRODUCTION_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.write(out + "\n")
        if err.strip():
            sys.stderr.write(err[-2000:] + "\n")
        if "ADMIN_MUSIC_FREE_DAILY_CREDITS_SETTING_PRODUCTION_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
