#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

REMOTE_PY = r'''
import asyncio, json, os
from collections import Counter
from pathlib import Path

for line in Path("/opt/camxora/repo/platform_api/.env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    k = k.strip()
    v = v.strip().strip('"').strip("'")
    if k.upper() in {"PLATFORM_CORS_ORIGINS", "CORS_ORIGINS"}:
        continue
    os.environ.setdefault(k, v)

import asyncpg
from platform_api.config import get_settings
from platform_api.dependencies import set_db_pool
from platform_api.services.admin_pipeline_service import list_admin_pipeline_board

async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    try:
        rows = await pool.fetch(
            """
            SELECT left(b.id::text,8) AS batch, b.status, b.song_count,
                   left(coalesce(b.ok_run_dir,''),40) AS ok_run
            FROM batches b ORDER BY created_at DESC LIMIT 8
            """
        )
        print("=== DB BATCHES ===")
        for r in rows:
            print(dict(r))

        assets = await pool.fetch(
            """
            WITH latest AS (SELECT id FROM batches ORDER BY created_at DESC LIMIT 8)
            SELECT left(a.batch_id::text,8) AS batch, a.role,
                   (a.background_16x9_path IS NOT NULL AND length(a.background_16x9_path)>0) AS has_bg,
                   (a.thumbnail_16x9_path IS NOT NULL AND length(a.thumbnail_16x9_path)>0) AS has_th,
                   a.pipeline_complete,
                   left(coalesce(a.background_16x9_path,''),50) AS bg
            FROM batch_channel_assets a JOIN latest l ON l.id=a.batch_id
            ORDER BY 1,2
            """
        )
        print("=== BATCH_CHANNEL_ASSETS ===")
        for r in assets:
            print(dict(r))

        images = await pool.fetch(
            """
            WITH latest AS (SELECT id FROM batches ORDER BY created_at DESC LIMIT 8)
            SELECT left(j.batch_id::text,8) AS batch, j.channel_role, j.kind, j.status, count(*)::int AS n
            FROM image_jobs j JOIN latest l ON l.id=j.batch_id
            GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
            """
        )
        print("=== IMAGE JOBS ===")
        for r in images:
            print(dict(r))

        active = await list_admin_pipeline_board(limit=40, active_only=True)
        print("=== ACTIVE COUNTS ===", json.dumps(active.get("counts"), default=str))
        print("=== ACTIVE BOARD ===")
        for r in active.get("rows") or []:
            meta = r.get("meta") or {}
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
                "notes": (r.get("notes") or "")[:90],
                "age_s": r.get("age_seconds"),
                "long_ready": meta.get("long_ready"),
                "pipeline_complete": meta.get("pipeline_complete"),
                "saved": meta.get("saved"),
                "expected": meta.get("expected"),
                "bg": f"{meta.get('bg_ready')}/{meta.get('bg_total')}",
                "meta_bg": bool(meta.get("background_16x9_path")),
                "run_dir": str(meta.get("run_dir") or "")[:55],
            }, default=str))

        all_rows = await list_admin_pipeline_board(limit=40, active_only=False)
        c = Counter((r.get("stage"), r.get("status")) for r in (all_rows.get("rows") or []))
        print("=== HIST include done ===")
        for k, v in c.most_common(25):
            print(v, k)
    finally:
        await pool.close()

asyncio.run(main())
'''


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
        sftp = client.open_sftp()
        with sftp.file("/tmp/diag_pipeline_board.py", "w") as rf:
            rf.write(REMOTE_PY)
        sftp.close()
        cmd = (
            "sudo -u camxora bash -lc "
            "'cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_pipeline_board.py'"
        )
        chan = client.get_transport().open_session()
        chan.settimeout(180)
        chan.exec_command(cmd)
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
        err = b""
        while chan.recv_stderr_ready():
            err += chan.recv_stderr(65535)
        if err:
            print("STDERR:", err.decode(errors="replace"), file=sys.stderr)
        print("exit", chan.recv_exit_status())
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
