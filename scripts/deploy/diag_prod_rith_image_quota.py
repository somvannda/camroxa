#!/usr/bin/env python3
"""Inspect Rith's 2026-08-19 image quota vs batches on production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


CMD = r'''
cd /opt/camxora/repo
export $(grep -E '^PLATFORM_DATABASE_URL=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
import asyncpg

def conv(v):
    if isinstance(v, (UUID, datetime, date, Decimal)):
        return str(v)
    return v

def rowdict(r):
    return {k: conv(r[k]) for k in r.keys()}

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    uid = "ddea20fa-66f5-40f1-9de9-05445e5825f8"
    out = {}
    out["image_jobs_updated_today"] = [
        rowdict(r) for r in await pool.fetch(
            """
            SELECT id, batch_id, kind, channel_role, status, attempt_count,
                   created_at, updated_at
            FROM image_jobs
            WHERE user_id = $1::uuid
              AND (updated_at AT TIME ZONE 'Asia/Bangkok')::date = DATE '2026-08-19'
            ORDER BY updated_at
            """,
            uid,
        )
    ]
    out["old_batch_image_jobs"] = [
        rowdict(r) for r in await pool.fetch(
            """
            SELECT id, kind, channel_role, status, attempt_count, created_at, updated_at
            FROM image_jobs
            WHERE batch_id = 'd667780d-4c12-43c5-bbcb-514850bccbc6'
            ORDER BY kind, channel_role
            """
        )
    ]
    out["run_image_jobs_today"] = [
        rowdict(r) for r in await pool.fetch(
            """
            SELECT id, status, attempts, batch_id, created_at, updated_at, payload
            FROM job_queue
            WHERE user_id = $1::uuid
              AND job_type = 'run_image_jobs'
              AND created_at >= TIMESTAMPTZ '2026-08-19 00:00:00+07'
            ORDER BY created_at
            """,
            uid,
        )
    ]
    print(json.dumps(out, indent=2, default=str))
    await pool.close()
asyncio.run(main())
PY
'''


def main() -> int:
    secrets = load_env("secrets.production.env")
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err, file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
