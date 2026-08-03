#!/usr/bin/env python3
"""Probe production for subscription-covers / credit display fix."""
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
    host = prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"]
    client = ssh_connect(
        host,
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        cmd = r"""
python3 - <<'PY'
from pathlib import Path
billing = Path('/opt/camxora/repo/platform_api/services/billing_mode_service.py').read_text()
batch = Path('/opt/camxora/repo/platform_api/services/batch_service.py').read_text()
print('billing.addon_slots', 'addon_slots' in billing)
print('billing.scaled_monthly', 'scaled_monthly' in billing)
print('batch.required_credits', 'required_credits = units_to_credits' in batch)
print('batch.raw_required_total', 'Required {total_wallet_cost}' in batch)
# show subscription_covers_batch signature
lines = billing.splitlines()
for i, line in enumerate(lines):
    if 'def subscription_covers_batch' in line:
        print('SIG', i+1, line.strip())
        for j in range(i, min(i+12, len(lines))):
            print(f'{j+1}:{lines[j]}')
        break
PY
"""
        _, stdout, stderr = client.exec_command(cmd, timeout=60)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print(err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
