"""Mint short-lived sandbox JWTs and compare v1/v3 wallet integers. No secrets printed."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

SANDBOX_HOST = "46.250.235.83"
CMD = r"""
set -e
if ip -4 addr | grep -q '82.197.71.248'; then echo REFUSE_PROD; exit 1; fi
sudo -u camxora bash -lc 'cd /opt/camxora/repo && platform_api/.venv/bin/python - <<"PY"
import json, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
import jwt
from platform_api.config import get_settings
import asyncio, asyncpg

EMAILS = [
    "kongsomvannda1987@gmail.com",
    "ksomvannda@gmail.com",
    "credits-cutover-test@sandbox.camxora.test",
    "duke@camxora.com",
]
settings = get_settings()

async def main():
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.connect(dsn)
    try:
        rows = await pool.fetch(
            "SELECT id, email, role, COALESCE(token_version,0) AS token_version FROM users WHERE email = ANY($1::text[])",
            EMAILS,
        )
    finally:
        await pool.close()
    now = datetime.now(timezone.utc)
    for row in rows:
        token = jwt.encode(
            {
                "user_id": str(row["id"]),
                "email": row["email"],
                "role": row["role"],
                "token_version": int(row["token_version"] or 0),
                "exp": now + timedelta(minutes=10),
                "iat": now,
                "type": "access",
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        def hit(path):
            req = urllib.request.Request(
                "https://api.sandbox.camxora.com" + path,
                headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.status, json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                try:
                    return exc.code, json.loads(raw)
                except Exception:
                    return exc.code, {"raw": raw[:200]}
        s3, v3 = hit("/api/v3/me/credits")
        s1, v1 = hit("/api/v1/credits/balance")
        s2, v2 = hit("/api/v1/v2/credits/balance")
        def unwrap(p):
            return p.get("data", p) if isinstance(p, dict) else p
        d3, d1, d2 = unwrap(v3), unwrap(v1), unwrap(v2)
        print(json.dumps({
            "email": row["email"],
            "v3": s3,
            "v3_balance": (d3 or {}).get("balance_credits") if isinstance(d3, dict) else None,
            "v1": s1,
            "v1_balance": (d1 or {}).get("balance") if isinstance(d1, dict) else None,
            "v2": s2,
            "v2_monthly": (d2 or {}).get("monthly_credits") if isinstance(d2, dict) else None,
            "v2_topup": (d2 or {}).get("topup_credits") if isinstance(d2, dict) else None,
        }))

asyncio.run(main())
PY'
"""


def load_sandbox() -> dict[str, str]:
    for root in (ROOT, Path(r"G:\Developments\Projects\Camxora\MusicGenerator")):
        path = root / ".deploy" / "secrets.sandbox.env"
        if path.is_file():
            break
    else:
        raise SystemExit("No secrets.sandbox.env")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_sandbox()
    host = secrets.get("SANDBOX_VPS_HOST") or secrets["VPS_HOST"]
    if host != SANDBOX_HOST:
        raise SystemExit(f"Refusing non-sandbox host: {host}")
    client = ssh_connect(
        host,
        secrets.get("SANDBOX_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("SANDBOX_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        print(stdout.read().decode("utf-8", "replace"))
        err = stderr.read().decode("utf-8", "replace")
        if err.strip():
            print(err[-1500:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
