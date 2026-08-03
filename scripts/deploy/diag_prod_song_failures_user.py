#!/usr/bin/env python3
"""List today's song failure reasons for somvannda on production."""
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
import asyncio, os, asyncpg
UID = "2baeaae8-0121-4d98-872d-eff832237f46"

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    # discover songs columns first
    cols = await pool.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name='songs' ORDER BY ordinal_position
        """
    )
    print("song_cols", [c["column_name"] for c in cols])
    err_col = None
    names = {c["column_name"] for c in cols}
    for cand in ("error_message", "error", "last_error", "failure_reason"):
        if cand in names:
            err_col = cand
            break
    print("err_col", err_col)
    if not err_col:
        await pool.close()
        return
    q = f"""
    SELECT status, count(*)::int AS n, left(coalesce({err_col}, ''), 140) AS err
    FROM songs
    WHERE user_id = $1::uuid
      AND updated_at >= (CURRENT_DATE AT TIME ZONE 'UTC')
    GROUP BY 1, 3
    ORDER BY n DESC
    LIMIT 25
    """
    rows = await pool.fetch(q, UID)
    print("today_song_status_groups")
    for r in rows:
        print(dict(r))
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
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
