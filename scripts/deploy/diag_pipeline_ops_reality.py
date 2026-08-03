#!/usr/bin/env python3
"""DB-level pipeline status reality check for production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
CMD = r"""
set +e
echo === RECENT BATCHES + ASSETS ===
sudo -u postgres psql -d camxora_platform -c "
SELECT b.id::text AS batch,
       b.status,
       b.song_count,
       left(coalesce(b.ok_run_dir,''),40) AS ok_run,
       left(coalesce(b.alt_run_dir,''),40) AS alt_run,
       b.created_at
FROM batches b
ORDER BY b.created_at DESC
LIMIT 12;
"
echo === SONG STATUS FOR LATEST 8 BATCHES ===
sudo -u postgres psql -d camxora_platform -c "
WITH latest AS (
  SELECT id FROM batches ORDER BY created_at DESC LIMIT 8
)
SELECT left(s.batch_id::text,8) AS batch, s.status, count(*)
FROM songs s
JOIN latest l ON l.id = s.batch_id
GROUP BY 1,2
ORDER BY 1,2;
"
echo === IMAGE JOBS LATEST ===
sudo -u postgres psql -d camxora_platform -c "
WITH latest AS (
  SELECT id FROM batches ORDER BY created_at DESC LIMIT 8
)
SELECT left(j.batch_id::text,8) AS batch, j.channel_role, j.kind, j.status, count(*)
FROM image_jobs j
JOIN latest l ON l.id = j.batch_id
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;
"
echo === CHANNEL ASSETS READY ===
sudo -u postgres psql -d camxora_platform -c "
WITH latest AS (
  SELECT id FROM batches ORDER BY created_at DESC LIMIT 8
)
SELECT left(a.batch_id::text,8) AS batch,
       a.channel_role,
       (a.background_16x9_path IS NOT NULL) AS has_bg,
       (a.thumbnail_16x9_path IS NOT NULL) AS has_th,
       a.long_ready,
       a.reel_ready,
       a.pipeline_complete,
       left(coalesce(a.run_dir,''),50) AS run_dir
FROM channel_assets a
JOIN latest l ON l.id = a.batch_id
ORDER BY 1,2;
"
echo === YOUTUBE / STREAM ===
sudo -u postgres psql -d camxora_platform -c "
WITH latest AS (
  SELECT id FROM batches ORDER BY created_at DESC LIMIT 8
)
SELECT 'yt' AS kind, left(y.batch_id::text,8) AS batch, y.status, count(*)
FROM youtube_upload_jobs y JOIN latest l ON l.id=y.batch_id
GROUP BY 1,2,3
UNION ALL
SELECT 'stream', left(s.batch_id::text,8), s.status, count(*)
FROM stream_upload_jobs s JOIN latest l ON l.id=s.batch_id
GROUP BY 1,2,3
ORDER BY 1,2,3;
"
echo === API BOARD VIA CURL WITH TOKEN IF ANY ===
# Use a throwaway service account? skip — use python against running app openapi path via unix? 
# Hit local API with a temporary script using app factory
sudo -u camxora bash -lc 'cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'"'"'PY'"'"'
import asyncio, json, os
from collections import Counter
os.environ.pop("PLATFORM_CORS_ORIGINS", None)
os.environ.pop("CORS_ORIGINS", None)
# Prefer DATABASE_URL already in process env from systemd? pull from .env carefully
from pathlib import Path
for line in Path("/opt/camxora/repo/platform_api/.env").read_text().splitlines():
    line=line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k,_,v=line.partition("=")
    k=k.strip(); v=v.strip().strip("\"").strip("\"")
    if k.upper() in {"PLATFORM_CORS_ORIGINS","CORS_ORIGINS"}:
        continue
    os.environ.setdefault(k, v)

import asyncpg
from platform_api.config import get_settings
from platform_api.dependencies import set_db_pool
from platform_api.services.admin_pipeline_service import list_admin_pipeline_board

async def main():
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    set_db_pool(pool)
    try:
        active = await list_admin_pipeline_board(limit=40, active_only=True)
        print("ACTIVE_COUNTS", json.dumps(active.get("counts"), default=str))
        for r in active.get("rows") or []:
            meta=r.get("meta") or {}
            print(json.dumps({
              "user": r.get("user_email"),
              "batch": (r.get("batch_id") or "")[:8],
              "role": r.get("role"),
              "stage": r.get("stage"),
              "status": r.get("status"),
              "music": r.get("music"),
              "image": r.get("image"),
              "converter": r.get("converter"),
              "merge": r.get("merge"),
              "youtube": r.get("youtube"),
              "streaming": r.get("streaming"),
              "notes": (r.get("notes") or "")[:80],
              "age_s": r.get("age_seconds"),
              "long_ready": meta.get("long_ready"),
              "pipeline_complete": meta.get("pipeline_complete"),
              "run_dir": str(meta.get("run_dir") or "")[:50],
            }, default=str))
        all_rows = await list_admin_pipeline_board(limit=40, active_only=False)
        c=Counter((r.get("stage"), r.get("status")) for r in (all_rows.get("rows") or []))
        print("HIST")
        for k,v in c.most_common(20):
            print(v, k)
    finally:
        await pool.close()
asyncio.run(main())
PY'
echo DONE
"""


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        chan = client.get_transport().open_session()
        chan.settimeout(180)
        chan.exec_command(CMD)
        out = b""
        while True:
            if chan.recv_ready():
                chunk = chan.recv(65535)
                if not chunk:
                    break
                out += chunk
            if chan.exit_status_ready():
                while chan.recv_ready():
                    out += chan.recv(65535)
                break
        print(out.decode(errors="replace"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
