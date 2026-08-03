#!/usr/bin/env python3
"""Count suno tasks and absorb cadence for the hot batch."""
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
from datetime import datetime

UID = "2baeaae8-0121-4d98-872d-eff832237f46"
BATCH = "8fcf1575-c831-41c3-a62e-42f08d1c7381"
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

    songs = await pool.fetch(
        "SELECT id, batch_index, status, title FROM songs WHERE batch_id=$1::uuid ORDER BY batch_index",
        BATCH,
    )
    print("SONGS", len(songs))
    for s in songs:
        print(s["batch_index"], s["status"], s["id"], s["title"])

    tasks = await pool.fetch(
        "SELECT id, song_id, status, error_message, created_at, updated_at "
        "FROM suno_tasks WHERE batch_id=$1::uuid ORDER BY created_at",
        BATCH,
    )
    print("BATCH_SUNO_TASKS", len(tasks))
    by_song = Counter(str(t["song_id"]) for t in tasks)
    by_status = Counter(str(t["status"]) for t in tasks)
    print("TASKS_BY_STATUS", dict(by_status))
    print("TASKS_PER_SONG")
    for k, v in by_song.most_common():
        print(v, k)
    print("SAMPLE_ERRORS")
    for t in tasks[-10:]:
        err = (t["error_message"] or "")[:160].replace("\n", " ")
        print(t["created_at"], t["status"], t["song_id"], err)

    # absorb spacing for top song
    rows = await pool.fetch(
        "SELECT created_at FROM credit_transactions "
        "WHERE user_id=$1::uuid AND ref_id=$2 AND reason='suno_generation_failed' "
        "AND created_at >= '2026-08-03'::timestamptz ORDER BY created_at",
        UID,
        "6686d795-2b34-479e-acee-e1ed66b2606e",
    )
    print("ABSORB_TIMESTAMPS", len(rows))
    prev = None
    gaps = []
    for r in rows:
        ts = r["created_at"]
        if prev is not None:
            gaps.append((ts - prev).total_seconds())
        prev = ts
    if gaps:
        print("GAP_SEC min/median/max", min(gaps), sorted(gaps)[len(gaps)//2], max(gaps))
        print("GAPS_UNDER_5S", sum(1 for g in gaps if g < 5))
        print("GAPS_UNDER_60S", sum(1 for g in gaps if g < 60))

    # plan vs wallet music debits today
    debit = await pool.fetch(
        "SELECT metadata->>'billing' billing, count(*) n, coalesce(sum(amount),0) amt "
        "FROM credit_transactions WHERE user_id=$1::uuid "
        "AND created_at >= '2026-08-03'::timestamptz "
        "AND (reason ILIKE '%suno%' OR metadata->>'operation'='music') "
        "GROUP BY 1",
        UID,
    )
    print("MUSIC_TXN_BILLING")
    for r in debit:
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
    client = ssh_connect(
        prod.get("PRODUCTION_VPS_HOST") or prod["VPS_HOST"],
        prod.get("PRODUCTION_VPS_USER") or prod["VPS_USER"],
        ensure_deploy_key(),
        prod.get("PRODUCTION_VPS_PASSWORD") or prod.get("VPS_PASSWORD"),
    )
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/diag_absorb_batch.py", "w") as remote:
            remote.write(REMOTE_PY)
        sftp.close()
        _, stdout, stderr = client.exec_command(
            "cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_absorb_batch.py",
            timeout=120,
        )
        print(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err[:2000], file=sys.stderr)
    finally:
        client.close()


if __name__ == "__main__":
    main()
