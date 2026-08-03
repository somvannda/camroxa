#!/usr/bin/env python3
"""Sandbox: provider key balances API + admin dashboard panel."""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

API_FILES = [
    "platform_api/services/provider_key_balance_service.py",
    "platform_api/services/suno_balance_service.py",
    "platform_api/services/key_pool_service.py",
    "platform_api/routers/admin.py",
    "platform_api/dependencies.py",
    "platform_api/wire_dependencies.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-02-admin-provider-key-balances.md",
]

ADMIN_FILES = [
    "admin_portal/src/types/provider-balances.ts",
    "admin_portal/src/hooks/use-dashboard.ts",
    "admin_portal/src/components/dashboard/provider-key-balances-panel.tsx",
    "admin_portal/src/pages/dashboard.tsx",
    "admin_portal/CHANGELOG.md",
]

SANDBOX_HOST = "46.250.235.83"


def load_sandbox() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.sandbox.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"Target sandbox host: {host}")

    archive = Path(tempfile.mkdtemp(prefix="balances-sbx-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in API_FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/provider-balances-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        for rel in ADMIN_FILES:
            local = ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/provider-balances-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal $REPO/docs/changelog; "
            "systemctl restart camxora-api; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'; "
            "sleep 2; "
            "systemctl is-active camxora-api; "
            "echo PROVIDER_BALANCES_SANDBOX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
