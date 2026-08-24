#!/usr/bin/env python3
"""Sandbox feature deploy: user portal Guides slide deck.

Path-scoped upload of Guides sources + nav, then rebuild/restart portal.
Not a production hotfix — ships the new Guides feature to sandbox only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"

FILES = [
    "website/CHANGELOG.md",
    "website/src/app/pricing/page.tsx",
    "website/src/app/pricing/pricing-cards.tsx",
    "website/src/lib/credits-only-public.ts",
    "website/src/lib/site-urls.ts",
    "docs/changelog/2026-08-23-desktop-paid-gate-and-website-pricing.md",
]

def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    path = None
    for root in (ROOT, Path(r"D:\\Development\\Projects\\Electron\\MusicGenerator")):
        cand = root / ".deploy" / name
        if cand.is_file():
            path = cand
            break
    if path is None:
        raise SystemExit("missing secrets")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    sb = load_env("secrets.sandbox.env")
    host = sb.get("SANDBOX_VPS_HOST") or sb["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")

    print(f"=== Feature deploy: user portal Guides -> sandbox ({host}) ===")
    client = ssh_connect(
        host,
        sb.get("SANDBOX_VPS_USER") or sb["VPS_USER"],
        ensure_deploy_key(),
        sb.get("SANDBOX_VPS_PASSWORD") or sb.get("VPS_PASSWORD"),
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
            "chown -R camxora:camxora /opt/camxora/repo/website /opt/camxora/repo/docs/changelog; "
            "sudo -u camxora bash -lc 'cd /opt/camxora/repo/website && npm run build'; "
            "systemctl restart camxora-website; "
            "sleep 2; "
            "systemctl is-active camxora-website; "
            "test -f /opt/camxora/repo/website/src/app/pricing/pricing-cards.tsx; "
            "grep -n 'Choose Your Plan\\|credits per month' /opt/camxora/repo/website/src/app/pricing/pricing-cards.tsx | head -5; "
            "echo WEBSITE_CREDITS_PRICING_DONE"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        safe = out.encode("ascii", errors="replace").decode("ascii")
        print(safe)
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
        if "WEBSITE_CREDITS_PRICING_DONE" not in out:
            raise SystemExit("Sandbox Guides feature deploy did not finish cleanly.")
        log_path = DEPLOY / "deploy-user-portal-guides-sandbox.log"
        log_path.write_text(out + "\n--- STDERR ---\n" + err, encoding="utf-8")
        print(f"Logged full output to {log_path}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
