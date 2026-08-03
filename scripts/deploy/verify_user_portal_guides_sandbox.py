#!/usr/bin/env python3
"""Smoke-check sandbox Guides feature after deploy."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"


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
    sb = load_env("secrets.sandbox.env")
    host = sb.get("SANDBOX_VPS_HOST") or sb["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(
        host,
        sb.get("SANDBOX_VPS_USER") or sb["VPS_USER"],
        ensure_deploy_key(),
        sb.get("SANDBOX_VPS_PASSWORD") or sb.get("VPS_PASSWORD"),
    )
    try:
        cmd = (
            "systemctl is-active camxora-portal; "
            "test -f /opt/camxora/repo/user_portal/src/app/dashboard/guides/page.tsx && echo guides_src_ok; "
            "grep -n 'href: \"/dashboard/guides\"' "
            "/opt/camxora/repo/user_portal/src/components/dashboard/control-panel-shell.tsx; "
            "ls /opt/camxora/repo/user_portal/.next/server/app/dashboard/guides 2>/dev/null | head -10; "
            "curl -sS -m 10 -o /dev/null -w 'guides_http:%{http_code}\\n' "
            "https://app.sandbox.camxora.com/dashboard/guides || true"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=60)
        out = stdout.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
