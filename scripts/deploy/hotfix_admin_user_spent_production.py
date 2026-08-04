#!/usr/bin/env python3
"""Production: User Spent admin page + /admin/user-spend API.

File-scoped hotfix — run only when explicitly asked for production.
"""
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
    "platform_api/services/cogs_estimate.py",
    "platform_api/services/user_spend_service.py",
    "platform_api/repositories/credit_repo.py",
    "platform_api/routers/admin.py",
    "platform_api/wire_dependencies.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-04-admin-user-spent.md",
]

ADMIN_FILES = [
    "admin_portal/src/pages/user-spent/index.tsx",
    "admin_portal/src/hooks/use-user-spend.ts",
    "admin_portal/src/types/api.ts",
    "admin_portal/src/types/models.ts",
    "admin_portal/src/App.tsx",
    "admin_portal/src/components/layout/sidebar.tsx",
    "admin_portal/src/pages/streaming/catalog.tsx",
    "admin_portal/CHANGELOG.md",
]

PRODUCTION_HOST = "82.197.71.248"


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== File-scoped deploy: User Spent -> production ({host}) ===")

    archive = Path(tempfile.mkdtemp(prefix="user-spent-prod-")) / "api.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for rel in API_FILES:
            path = ROOT / rel
            if not path.is_file():
                raise FileNotFoundError(path)
            tar.add(path, arcname=rel.replace("\\", "/"))

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/user-spent-api.tar.gz", "wb") as remote:
            remote.write(archive.read_bytes())
        print(f"Uploaded API archive ({len(API_FILES)} files)")

        for rel in ADMIN_FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote_path = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote_path.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote_path, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "tar -xzf /tmp/user-spent-api.tar.gz -C $REPO; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal $REPO/docs/changelog; "
            "systemctl restart camxora-api; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'; "
            "sleep 2; "
            "systemctl is-active camxora-api; "
            "echo USER_SPENT_PRODUCTION_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        snippet = out[-8000:] if len(out) > 8000 else out
        sys.stdout.buffer.write(snippet.encode("utf-8", errors="replace") + b"\n")
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:].encode("utf-8", errors="replace") + b"\n")
        if "USER_SPENT_PRODUCTION_DONE" not in out:
            return 1
        print("USER_SPENT_PRODUCTION_DONE")
        return 0
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
