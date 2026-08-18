#!/usr/bin/env python3
"""File-scoped production hotfix: Progress generation-complete vs export-ready.

Allowlisted paths only. Does not sync music-web or other dirty workspace files.
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
FILES = [
    "platform_api/routers/progress.py",
    "platform_api/services/channel_asset_service.py",
    "platform_api/services/admin_pipeline_service.py",
    "platform_api/CHANGELOG.md",
    "docs/changelog/2026-08-16-progress-trust-image-job-success.md",
]


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== File-scoped Progress hotfix -> production ({host}) ===")
    print(f"File source: {ROOT}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            parent = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {parent}")
            print(f"Uploading {rel}")
            sftp.put(str(local), remote)
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/routers/progress.py \
  $REPO/platform_api/services/channel_asset_service.py \
  $REPO/platform_api/services/admin_pipeline_service.py \
  $REPO/platform_api/CHANGELOG.md \
  $REPO/docs/changelog/2026-08-16-progress-trust-image-job-success.md
grep -n '_image_jobs_complete\|_export_assets_verified' $REPO/platform_api/routers/progress.py | head
grep -n 'mark_ready_from_image_jobs' $REPO/platform_api/routers/progress.py && echo 'UNEXPECTED mark_ready in progress.py' && exit 1 || true
grep -n 'Do not use this on desktop GET /progress' $REPO/platform_api/services/channel_asset_service.py | head
systemctl restart camxora-api
sleep 3
systemctl is-active camxora-api
curl -sf -o /dev/null -w 'health:%{http_code}\n' https://api.camxora.com/health
echo PROGRESS_IMAGE_HOTFIX_OK
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=90)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:], file=sys.stderr)
        if "PROGRESS_IMAGE_HOTFIX_OK" not in out:
            return 1
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
