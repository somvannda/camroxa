#!/usr/bin/env python3
"""File-scoped admin UI hotfix: Credits column used/total.

Does not restart the API. Rebuilds admin_portal only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)

SANDBOX_HOST = "46.250.235.83"
PRODUCTION_HOST = "82.197.71.248"
REMOTE_REPO = "/opt/camxora/repo"
DBG = ROOT / ".dbg" / "prod_admin_free_daily"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=("sandbox", "production"), required=True)
    args = parser.parse_args()

    if args.env == "production":
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)
        if host != PRODUCTION_HOST:
            raise SystemExit(f"Refusing non-production host: {host}")
        uploads = [
            (DBG / "index.tsx", f"{REMOTE_REPO}/admin_portal/src/pages/users/index.tsx"),
            (DBG / "user-detail.tsx", f"{REMOTE_REPO}/admin_portal/src/pages/users/user-detail.tsx"),
        ]
        health = "http://127.0.0.1:8100/health"
        index_src = DBG / "index.tsx"
    else:
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
        if host != SANDBOX_HOST:
            raise SystemExit(f"Refusing non-sandbox host: {host}")
        uploads = [
            (
                ROOT / "admin_portal/src/pages/users/index.tsx",
                f"{REMOTE_REPO}/admin_portal/src/pages/users/index.tsx",
            ),
            (
                ROOT / "admin_portal/src/pages/users/user-detail.tsx",
                f"{REMOTE_REPO}/admin_portal/src/pages/users/user-detail.tsx",
            ),
        ]
        health = "http://127.0.0.1:8100/health"
        index_src = ROOT / "admin_portal/src/pages/users/index.tsx"

    text = index_src.read_text(encoding="utf-8")
    if "credits_burned != null" not in text or "music_credits_limit.toLocaleString()" not in text:
        raise SystemExit("Credits used/total display is missing from the local Users table")

    print(f"=== Credits used/total -> {args.env} ({host}) ===")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for local, remote in uploads:
            if not local.is_file():
                raise FileNotFoundError(local)
            with sftp.file(remote, "wb") as remote_file:
                remote_file.write(local.read_bytes())
            print(f"Uploaded {local.as_posix()} -> {remote}")
        sftp.close()

        cmd = rf"""
set -e
REPO=/opt/camxora/repo
chown -R camxora:camxora \
  $REPO/admin_portal/src/pages/users/index.tsx \
  $REPO/admin_portal/src/pages/users/user-detail.tsx
grep -n "credits_burned != null" $REPO/admin_portal/src/pages/users/index.tsx | head
code=$(curl -sS -m 3 -o /dev/null -w '%{{http_code}}' {health} || true)
echo api_health=$code
test "$code" = "200"
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && npm run build'
echo CREDITS_USED_TOTAL_DONE
"""
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read()
        err = stderr.read()
        sys.stdout.buffer.write(out + b"\n")
        if err.strip():
            sys.stderr.buffer.write(err[-2000:] + b"\n")
        if b"CREDITS_USED_TOTAL_DONE" not in out:
            return 1
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
