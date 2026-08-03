#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402


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
    client = ssh_connect(
        prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"],
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, _ = client.exec_command(
            "grep -n 'def scaled_monthly_limit' "
            "/opt/camxora/repo/platform_api/services/plan_tier_pricing_service.py "
            "|| echo MISSING_SCALED_MONTHLY"
        )
        print(stdout.read().decode(errors="replace"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
