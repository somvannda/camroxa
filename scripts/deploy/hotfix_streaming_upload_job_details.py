#!/usr/bin/env python3
"""Hotfix enriched streaming upload-jobs admin detail (sandbox/production)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

API_FILES = [
    "platform_api/repositories/streaming_repo.py",
    "platform_api/routers/streaming_admin.py",
    "platform_api/services/streaming_upload_service.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-02-admin-streaming-upload-job-details.md",
]

ADMIN_FILES = [
    "admin_portal/src/pages/streaming/upload-jobs.tsx",
    "admin_portal/src/hooks/use-streaming.ts",
    "admin_portal/CHANGELOG.md",
]

SANDBOX_HOST = "46.250.235.83"
PRODUCTION_HOST = "82.197.71.248"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def deploy(host: str, user: str, password: str | None, label: str) -> None:
    print(f"=== Streaming upload-job details hotfix → {label} ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in API_FILES + ADMIN_FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote_path = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote_path.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote_path, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = (
            "set -e; "
            "REPO=/opt/camxora/repo; "
            "chown -R camxora:camxora $REPO/platform_api $REPO/admin_portal $REPO/docs/changelog; "
            "systemctl restart camxora-api; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'; "
            "sleep 4; "
            "systemctl is-active camxora-api; "
            "curl -sS -m 10 -o /dev/null -w 'upload-jobs:%{http_code}\\n' "
            "http://127.0.0.1:8100/api/v1/admin/streaming/upload-jobs; "
            "grep -n 'stream_album_name\\|user_display_name' "
            "$REPO/platform_api/routers/streaming_admin.py | head -8; "
            "echo STREAMING_UPLOAD_JOB_DETAILS_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()


def main() -> int:
    target = (sys.argv[1] if len(sys.argv) > 1 else "sandbox").strip().lower()
    if target in {"sandbox", "both"}:
        sb = load_env("secrets.sandbox.env")
        host = sb.get("SANDBOX_VPS_HOST") or sb["VPS_HOST"]
        if host != SANDBOX_HOST:
            raise SystemExit(f"Refusing non-sandbox host: {host}")
        deploy(
            host,
            sb.get("SANDBOX_VPS_USER") or sb["VPS_USER"],
            sb.get("SANDBOX_VPS_PASSWORD") or sb.get("VPS_PASSWORD"),
            "sandbox",
        )
    if target in {"production", "prod", "both"}:
        pr = load_env("secrets.production.env")
        host = pr.get("PRODUCTION_VPS_HOST") or pr["VPS_HOST"]
        if host != PRODUCTION_HOST:
            raise SystemExit(f"Refusing non-production host: {host}")
        deploy(
            host,
            pr.get("PRODUCTION_VPS_USER") or pr["VPS_USER"],
            pr.get("PRODUCTION_VPS_PASSWORD") or pr.get("VPS_PASSWORD"),
            "production",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
