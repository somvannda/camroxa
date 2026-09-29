#!/usr/bin/env python3
"""Production rollout for the $79 desktop renew flow + free video/merge.

Assumes platform_api was already synced (sync_platform_api_production.py).
  1. run alembic upgrade head (applies 124_free_local_video_merge)
  2. upload the changed user_portal files, rebuild, restart camxora-portal
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

FILES = [
    "user_portal/src/lib/billing.ts",
    "user_portal/src/app/dashboard/billing/page.tsx",
    "user_portal/src/components/dashboard/quota-renewal-card.tsx",
    "user_portal/src/components/quota-renewal-card.tsx",
]


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    prod = load_env("secrets.production.env")
    host = prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    print(f"=== Desktop renewal production rollout -> {host} ===")
    client = ssh_connect(
        host,
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = ROOT / rel
            if not local.is_file():
                raise FileNotFoundError(local)
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            remote_dir = "/".join(remote.split("/")[:-1])
            client.exec_command(f"mkdir -p {remote_dir}")
            with sftp.file(remote, "wb") as rf:
                rf.write(local.read_bytes())
            print(f"Uploaded {rel}")
        sftp.close()

        cmd = (
            "set -e; "
            "chown -R camxora:camxora /opt/camxora/repo/user_portal; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && .venv/bin/alembic upgrade head'; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/platform_api && .venv/bin/alembic current'; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/user_portal && npm run build'; "
            "systemctl restart camxora-portal; "
            "sleep 2; "
            "systemctl is-active camxora-api camxora-portal; "
            "grep -c quota-renewal-card /opt/camxora/repo/user_portal/src/app/dashboard/billing/page.tsx; "
            "ls /opt/camxora/repo/user_portal/.next/server/app/dashboard/billing 2>/dev/null | head -5; "
            "echo DESKTOP_RENEWAL_PROD_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=1200)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if "DESKTOP_RENEWAL_PROD_DONE" not in out:
            raise SystemExit("Production rollout did not finish cleanly (check output above).")
        (DEPLOY / "deploy-desktop-renewal-production.log").write_text(
            out + "\n--- STDERR ---\n" + err, encoding="utf-8"
        )
        print("Logged to scripts/deploy/deploy-desktop-renewal-production.log")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
