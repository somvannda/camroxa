#!/usr/bin/env python3
"""Restore provider-balance dashboard files + Force-update publish fix on production admin."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_ROOT = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")


def main() -> int:
    sources = [
        (
            MAIN_ROOT / "admin_portal/src/types/provider-balances.ts",
            "/opt/camxora/repo/admin_portal/src/types/provider-balances.ts",
        ),
        (
            MAIN_ROOT / "admin_portal/src/components/dashboard/provider-key-balances-panel.tsx",
            "/opt/camxora/repo/admin_portal/src/components/dashboard/provider-key-balances-panel.tsx",
        ),
        (
            MAIN_ROOT / "admin_portal/src/hooks/use-dashboard.ts",
            "/opt/camxora/repo/admin_portal/src/hooks/use-dashboard.ts",
        ),
        (
            MAIN_ROOT / "admin_portal/src/pages/dashboard.tsx",
            "/opt/camxora/repo/admin_portal/src/pages/dashboard.tsx",
        ),
        (
            REPO_ROOT / "admin_portal/src/components/software-updates/release-editor-dialog.tsx",
            "/opt/camxora/repo/admin_portal/src/components/software-updates/release-editor-dialog.tsx",
        ),
        (
            REPO_ROOT / "admin_portal/src/components/software-updates/installer-files-table.tsx",
            "/opt/camxora/repo/admin_portal/src/components/software-updates/installer-files-table.tsx",
        ),
        (
            REPO_ROOT / "admin_portal/src/hooks/use-desktop-notifications.ts",
            "/opt/camxora/repo/admin_portal/src/hooks/use-desktop-notifications.ts",
        ),
    ]

    for local, _remote in sources:
        if not local.is_file():
            print(f"Missing local file: {local}")
            return 1

    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    _, stdout, _ = client.exec_command(
        "mkdir -p "
        "/opt/camxora/repo/admin_portal/src/types "
        "/opt/camxora/repo/admin_portal/src/components/dashboard "
        "/opt/camxora/repo/admin_portal/src/components/software-updates "
        "/opt/camxora/repo/admin_portal/src/hooks "
        "/opt/camxora/repo/admin_portal/src/pages"
    )
    stdout.channel.recv_exit_status()

    sftp = client.open_sftp()
    for local, remote in sources:
        print(f"Uploading {local.as_posix()} -> {remote}")
        sftp.put(str(local), remote)
    sftp.close()

    cmd = r"""
set -e
chown -R camxora:camxora /opt/camxora/repo/admin_portal/src
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
echo ADMIN_HOTFIX_DONE
"""
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    client.close()
    snippet = out[-8000:] if len(out) > 8000 else out
    sys.stdout.buffer.write(snippet.encode("utf-8", errors="replace") + b"\n")
    if err.strip():
        sys.stdout.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
