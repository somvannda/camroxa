#!/usr/bin/env python3
"""File-scoped hotfix: software-update Force-update publish fix (admin UI).

Uploads only the three changed admin files, removes an orphan dashboard panel
that can break `tsc` when left behind by a partial earlier deploy, then rebuilds.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

FILES = (
    "admin_portal/src/components/software-updates/release-editor-dialog.tsx",
    "admin_portal/src/components/software-updates/installer-files-table.tsx",
    "admin_portal/src/hooks/use-desktop-notifications.ts",
)

# Orphan from a partial earlier deploy; breaks tsc when use-dashboard lacks the hook.
ORPHAN_REMOTE_PATHS = (
    "/opt/camxora/repo/admin_portal/src/components/dashboard/provider-key-balances-panel.tsx",
    "/opt/camxora/repo/admin_portal/src/types/provider-balances.ts",
)


def _deploy(env: str) -> int:
    if env == "production":
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)
    else:
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
    print(f"Target {env} host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    sftp = client.open_sftp()
    for rel in FILES:
        local = REPO_ROOT / rel
        remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
        print(f"Uploading {rel} -> {remote}")
        sftp.put(str(local), remote)
    sftp.close()

    orphans = " ".join(ORPHAN_REMOTE_PATHS)
    cmd = f"""
set -e
REPO=/opt/camxora/repo
rm -f {orphans}
# Drop dashboard imports of the orphan panel if present (best-effort sed).
if [ -f $REPO/admin_portal/src/pages/dashboard.tsx ]; then
  sed -i '/provider-key-balances-panel/d' $REPO/admin_portal/src/pages/dashboard.tsx || true
fi
chown -R camxora:camxora $REPO/admin_portal/src
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


def main() -> int:
    env = "sandbox"
    if len(sys.argv) > 1 and sys.argv[1] in {"sandbox", "production"}:
        env = sys.argv[1]
    return _deploy(env)


if __name__ == "__main__":
    raise SystemExit(main())
