#!/usr/bin/env python3
"""File-scoped sandbox hotfix: profile current plan + my-subscription LEFT JOIN."""

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
    "platform_api/services/v2/subscription_service.py",
    "platform_api/services/v2/credit_service.py",
    "platform_api/routers/v2_subscriptions.py",
    "platform_api/routers/v2_credits.py",
    "music_web/src/lib/subscription-api.ts",
    "music_web/src/components/subscription-section.tsx",
    "music_web/src/components/available-plans-grid.tsx",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    print(f"=== Profile current-plan hotfix -> sandbox ({host}) ===")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in UPLOADS:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = r"""
set -e
REPO=/opt/camxora/repo
chown camxora:camxora \
  $REPO/platform_api/services/v2/subscription_service.py \
  $REPO/platform_api/services/v2/credit_service.py \
  $REPO/platform_api/routers/v2_subscriptions.py \
  $REPO/platform_api/routers/v2_credits.py \
  $REPO/music_web/src/lib/subscription-api.ts \
  $REPO/music_web/src/components/subscription-section.tsx \
  $REPO/music_web/src/components/available-plans-grid.tsx
systemctl restart camxora-api
sudo -u camxora bash -lc 'cd /opt/camxora/repo/music_web && npm run build'
systemctl restart camxora-music
sleep 6
systemctl is-active camxora-api
systemctl is-active camxora-music
echo PROFILE_CURRENT_PLAN_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        try:
            print(out.encode("ascii", errors="replace").decode("ascii"))
        except UnicodeEncodeError:
            print("remote output omitted")
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"))
        if "PROFILE_CURRENT_PLAN_DONE" not in out:
            raise SystemExit("Sandbox profile current-plan hotfix did not finish cleanly.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
