#!/usr/bin/env python3
"""Production file-scoped deploy: user portal Guides slide deck.

Uploads only the Guides allowlist (same as sandbox feature ship), rebuilds
user_portal, restarts camxora-portal. Safe for a mixed local working tree —
does not sync unrelated dirty files.
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
    "user_portal/src/components/dashboard/control-panel-shell.tsx",
    "user_portal/src/app/dashboard/guides/page.tsx",
    "user_portal/src/app/dashboard/guides/deck.ts",
    "user_portal/src/app/dashboard/guides/guides-deck.tsx",
    "user_portal/src/app/dashboard/guides/slide-frame.tsx",
    "user_portal/src/app/dashboard/guides/slide-mocks.tsx",
    "user_portal/public/guides/README.md",
    "user_portal/CHANGELOG.md",
    "docs/changelog/2026-08-03-user-portal-guides-deck.md",
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

    print(f"=== File-scoped deploy: user portal Guides -> production ({host}) ===")
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
            "chown -R camxora:camxora /opt/camxora/repo/user_portal /opt/camxora/repo/docs/changelog; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/user_portal && npm run build'; "
            "systemctl restart camxora-portal; "
            "sleep 2; "
            "systemctl is-active camxora-portal; "
            "test -f /opt/camxora/repo/user_portal/src/app/dashboard/guides/page.tsx; "
            "grep -n 'Guides' /opt/camxora/repo/user_portal/src/components/dashboard/control-panel-shell.tsx | head -3; "
            "ls /opt/camxora/repo/user_portal/.next/server/app/dashboard/guides 2>/dev/null | head -10; "
            "echo USER_PORTAL_GUIDES_PRODUCTION_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        safe = out.encode("ascii", errors="replace").decode("ascii")
        print(safe)
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if "USER_PORTAL_GUIDES_PRODUCTION_DONE" not in out:
            raise SystemExit("Production Guides deploy did not finish cleanly.")
        log_path = DEPLOY / "deploy-user-portal-guides-production.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
