#!/usr/bin/env python3
"""Diagnose today's fail-absorb ledger for a production user."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

REMOTE_PY = r'''
import asyncio, os
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

UID = "2baeaae8-0121-4d98-872d-eff832237f46"
env_path = Path("platform_api/.env")
for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import asyncpg
import redis.asyncio as redis

SQL = (
    "SELECT created_at, amount, direction, reason, "
    "metadata->>'billing' AS billing, "
    "metadata->>'operation' AS operation, "
    "metadata->>'provider' AS provider, "
    "metadata->>'outcome' AS outcome, "
    "metadata->>'platform_absorbed_cost' AS absorbed, "
    "ref_id "
    "FROM credit_transactions "
    "WHERE user_id = $1::uuid "
    "AND created_at >= $2::timestamptz "
    "AND created_at < ($2::date + 1)::timestamptz "
    "ORDER BY created_at"
)

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    r = redis.from_url(os.environ["PLATFORM_REDIS_URL"], decode_responses=True)
    keys = []
    cur = 0
    while True:
        cur, batch = await r.scan(cursor=cur, match=f"fail_absorb:{UID}:*", count=50)
        keys.extend(batch)
        if cur == 0:
            break
    print("REDIS_KEYS", keys)
    for k in keys:
        print("REDIS", k, await r.get(k))

    day_start = datetime(2026, 8, 3, tzinfo=timezone.utc)
    try:
        rows = await pool.fetch(SQL, UID, day_start)
    except Exception as exc:
        print("LEDGER_QUERY_FAILED", type(exc).__name__, exc)
        cols = await pool.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='credit_transactions' ORDER BY ordinal_position"
        )
        print("COLS", [c["column_name"] for c in cols])
        await pool.close()
        await r.aclose()
        return

    print("LEDGER_ROWS_TODAY", len(rows))
    absorb_ops = Counter()
    absorb_reasons = Counter()
    absorb_detail = Counter()
    absorb_refs = Counter()
    for row in rows:
        if row["billing"] != "platform_absorb" and row["absorbed"] != "true":
            continue
        absorb_ops[row["operation"] or "?"] += 1
        absorb_reasons[row["reason"] or "?"] += 1
        absorb_detail[f"{row['operation']}/{row['provider']}/{row['reason']}"] += 1
        absorb_refs[str(row["ref_id"] or "?")[:36]] += 1
    print("ABSORB_TOTAL", sum(absorb_ops.values()))
    print("ABSORB_BY_OPERATION", dict(absorb_ops))
    print("ABSORB_BY_REASON", dict(absorb_reasons))
    print("ABSORB_DETAIL")
    for k, v in absorb_detail.most_common(40):
        print(f"  {v:3d}  {k}")
    print("TOP_REF_IDS")
    for k, v in absorb_refs.most_common(15):
        print(f"  {v:3d}  {k}")
    print("LAST_ABSORB")
    n = 0
    for row in reversed(rows):
        if row["billing"] != "platform_absorb" and row["absorbed"] != "true":
            continue
        print(
            row["created_at"].isoformat(),
            row["direction"],
            row["operation"],
            row["reason"],
            row["ref_id"],
        )
        n += 1
        if n >= 25:
            break
    await pool.close()
    await r.aclose()

asyncio.run(main())
'''


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> None:
    prod = load_env("secrets.production.env")
    host = prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"]
    user = prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"]
    password = prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        remote_path = "/tmp/diag_absorb_ledger.py"
        with sftp.file(remote_path, "w") as remote:
            remote.write(REMOTE_PY)
        sftp.close()
        cmd = (
            "cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_absorb_ledger.py"
        )
        _, stdout, stderr = client.exec_command(cmd, timeout=120)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err[:2000], file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    main()
