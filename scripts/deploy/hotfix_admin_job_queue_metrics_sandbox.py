#!/usr/bin/env python3
"""Sandbox: upload Job Queue admin UI files and rebuild admin_portal."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

FILES = [
    "admin_portal/src/types/job-queue.ts",
    "admin_portal/src/hooks/use-job-queue.ts",
    "admin_portal/src/pages/job-queue/index.tsx",
    "admin_portal/src/App.tsx",
    "admin_portal/src/components/layout/sidebar.tsx",
    "admin_portal/src/components/layout/top-bar.tsx",
    "admin_portal/CHANGELOG.md",
    "docs/changelog/2026-08-02-admin-job-queue-metrics-ui.md",
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

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = (
            "set -e; "
            "chown -R camxora:camxora /opt/camxora/repo/admin_portal /opt/camxora/repo/docs/changelog; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'; "
            "echo ADMIN_JOB_QUEUE_SANDBOX_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
