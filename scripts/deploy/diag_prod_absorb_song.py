#!/usr/bin/env python3
"""Inspect one song's suno tasks vs absorb refunds on production."""
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
from collections import Counter

UID = "2baeaae8-0121-4d98-872d-eff832237f46"
SONG = "6686d795-2b34-479e-acee-e1ed66b2606e"
for line in Path("platform_api/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
import asyncpg

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    song = await pool.fetchrow(
        "SELECT id, status, batch_id, batch_index, title, updated_at FROM songs WHERE id=$1::uuid",
        SONG,
    )
    print("SONG", dict(song) if song else None)

    # Discover suno task table/columns
    tables = await pool.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND (table_name ILIKE '%suno%' OR table_name ILIKE '%generation%')"
    )
    print("TABLES", [t["table_name"] for t in tables])

    for table in [t["table_name"] for t in tables]:
        cols = await pool.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=$1 ORDER BY ordinal_position",
            table,
        )
        names = [c["column_name"] for c in cols]
        if "song_id" in names:
            print("CANDIDATE", table, names[:20])

    # Try common tables
    for table in ("suno_tasks", "generation_tasks", "ai_tasks", "tasks"):
        try:
            rows = await pool.fetch(
                f"SELECT * FROM {table} WHERE song_id=$1::uuid ORDER BY created_at NULLS LAST LIMIT 5",
                SONG,
            )
        except Exception as exc:
            print("SKIP", table, type(exc).__name__, str(exc)[:120])
            continue
        print("ROWS", table, len(rows))
        if rows:
            print("KEYS", list(dict(rows[0]).keys()))
            for r in rows:
                d = dict(r)
                print({k: d.get(k) for k in list(d)[:12]})

    rows = await pool.fetch(
        "SELECT created_at, reason, metadata->>'billing' billing, amount, direction "
        "FROM credit_transactions "
        "WHERE user_id=$1::uuid AND ref_id=$2 AND created_at >= '2026-08-03'::timestamptz "
        "ORDER BY created_at",
        UID,
        SONG,
    )
    print("TXNS_FOR_SONG", len(rows))
    c = Counter((r["direction"], r["reason"], r["billing"], int(r["amount"] or 0)) for r in rows)
    for k, v in c.most_common():
        print(v, k)
    print("FIRST5")
    for r in rows[:5]:
        print(dict(r))
    print("LAST5")
    for r in rows[-5:]:
        print(dict(r))
    await pool.close()

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
        with sftp.file("/tmp/diag_absorb_song.py", "w") as remote:
            remote.write(REMOTE_PY)
        sftp.close()
        cmd = (
            "cd /opt/camxora/repo && "
            "PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_absorb_song.py"
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
