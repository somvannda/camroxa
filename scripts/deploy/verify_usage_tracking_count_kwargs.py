#!/usr/bin/env python3
"""Verify secondary attribution no longer TypeErrors on production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

REMOTE_PY = r'''
import asyncio, inspect, os
from pathlib import Path
from uuid import UUID

for line in Path("platform_api/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import asyncpg
import redis.asyncio as redis
from platform_api.repositories.usage_tracking_repo import UsageTrackingRepository
from platform_api.services.billing_calendar import billing_today

UID = UUID("2baeaae8-0121-4d98-872d-eff832237f46")

async def main():
    sig = str(inspect.signature(UsageTrackingRepository.increment_usage))
    print("SIGNATURE", sig)
    assert "count" in sig and "include_monthly" in sig

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    r = redis.from_url(os.environ["PLATFORM_REDIS_URL"], decode_responses=True)
    # confirm absorb cleared
    keys = []
    cur = 0
    while True:
        cur, batch = await r.scan(cursor=cur, match=f"fail_absorb:{UID}:*", count=50)
        keys.extend(batch)
        if cur == 0:
            break
    print("ABSORB_KEYS", {k: await r.get(k) for k in keys})

    # pick a secondary profile for the user if any
    profile = await pool.fetchrow(
        "SELECT id FROM channel_profiles WHERE user_id=$1::uuid ORDER BY created_at DESC LIMIT 1",
        str(UID),
    )
    if profile is None:
        print("NO_PROFILE")
        await pool.close()
        await r.aclose()
        return
    repo = UsageTrackingRepository(pool)
    # Call with the kwargs that used to TypeError — use a disposable in-memory check
    # via signature bind (no DB write).
    bound = inspect.signature(UsageTrackingRepository.increment_usage).bind(
        repo,
        user_id=UID,
        channel_profile_id=profile["id"],
        operation_type="music",
        usage_date=today,
        period_start=today.replace(day=1),
        count=1,
        include_monthly=False,
    )
    bound.apply_defaults()
    print("BIND_OK", list(bound.kwargs.keys()) if False else "count+include_monthly accepted")
    print("PROFILE", profile["id"])
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
    client = ssh_connect(
        prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"],
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/verify_usage_count.py", "w") as remote:
            remote.write(REMOTE_PY)
        sftp.close()
        _, stdout, stderr = client.exec_command(
            "cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/verify_usage_count.py; "
            "systemctl is-active camxora-api camxora-worker-suno@1 camxora-worker-suno@2",
            timeout=60,
        )
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err[:1500], file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    main()
