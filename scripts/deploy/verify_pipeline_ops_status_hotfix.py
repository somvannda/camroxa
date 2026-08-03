#!/usr/bin/env python3
"""Verify sandbox Pipeline Ops board status hotfix landed."""
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
            "systemctl is-active camxora-api; "
            "curl -sS -m 10 -o /dev/null -w 'board:%{http_code}\\n' "
            "http://127.0.0.1:8100/api/v1/admin/pipeline/board; "
            "grep -n '_promote_admin_stage\\|_trust_persisted_asset_paths' "
            "/opt/camxora/repo/platform_api/services/admin_pipeline_service.py | head -8"
        )
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=60)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
