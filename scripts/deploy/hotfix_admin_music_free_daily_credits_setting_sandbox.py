#!/usr/bin/env python3
"""File-scoped sandbox hotfix: admin Music Web free daily credits setting."""

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
        ROOT / "admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/plans/music-web-free-credits-section.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/plans/index.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/plans/index.tsx",
    ),
    (
        ROOT / "admin_portal/src/pages/settings/index.tsx",
        "/opt/camxora/repo/admin_portal/src/pages/settings/index.tsx",
    ),
    (
        ROOT / "admin_portal/CHANGELOG.md",
        "/opt/camxora/repo/admin_portal/CHANGELOG.md",
    ),
    (
        ROOT / "docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md",
        "/opt/camxora/repo/docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md",
    ),
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Admin Music Web free daily credits -> sandbox ({host}) ===")

    section = (
        ROOT / "admin_portal/src/pages/plans/music-web-free-credits-section.tsx"
    ).read_text(encoding="utf-8")
    if "web_music_free_daily_credits" not in section:
        raise SystemExit("music-web-free-credits-section.tsx is missing the setting key")

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
  $REPO/admin_portal/src/pages/plans/music-web-free-credits-section.tsx \
  $REPO/admin_portal/src/pages/plans/index.tsx \
  $REPO/admin_portal/src/pages/settings/index.tsx \
  $REPO/admin_portal/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-18-admin-music-free-daily-credits-setting.md
echo '=== credit service reads free daily setting? ==='
python3 - <<'PY'
from pathlib import Path
needles = ('web_music_free_daily_credits', 'daily_free_limit', 'WEB_MUSIC_CREDITS_PER_SONG')
roots = [
    Path('/opt/camxora/repo/platform_api/services'),
    Path('/opt/camxora/repo/platform_api'),
]
seen = set()
for root in roots:
    if not root.exists():
        continue
    for path in root.rglob('*.py'):
        text = path.read_text(encoding='utf-8', errors='replace')
        hits = [n for n in needles if n in text]
        if hits:
            rel = str(path)
            if rel in seen:
                continue
            seen.add(rel)
            print(f'{path}: {", ".join(hits)}')
PY
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
grep -n "MusicWebFreeCreditsSection\|web_music_free_daily_credits" \
  $REPO/admin_portal/src/pages/plans/index.tsx \
  $REPO/admin_portal/src/pages/settings/index.tsx \
  $REPO/admin_portal/src/pages/plans/music-web-free-credits-section.tsx | head
echo ADMIN_MUSIC_FREE_DAILY_CREDITS_SETTING_DONE
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
