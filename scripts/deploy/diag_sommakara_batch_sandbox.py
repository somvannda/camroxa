#!/usr/bin/env python3
"""Diagnose sommakara batch: downloads, streaming, images on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = '''
import asyncio
import json
import os
import asyncpg

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    try:
        user = await conn.fetchrow(
            "SELECT id, email, display_name FROM users WHERE email ILIKE '%sommakara%' OR display_name ILIKE '%sommakara%' LIMIT 5"
        )
        if not user:
            user = await conn.fetchrow(
                "SELECT id, email, display_name FROM users WHERE email ILIKE '%somvannda%' LIMIT 1"
            )
        print("USER:", json.dumps(dict(user) if user else None, default=str))
        if not user:
            return
        uid = user["id"]

        batches = await conn.fetch(
            "SELECT id, status, song_count, auto_gsuno, auto_gen_image, ok_run_dir, alt_run_dir, created_at, updated_at "
            "FROM batches WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
            uid,
        )
        print("\\n=== Recent batches ===")
        for b in batches:
            print(json.dumps(dict(b), default=str))
        batch_ids = [b["id"] for b in batches]

        print("\\n=== Suno tasks (latest batch) ===")
        if batch_ids:
            tasks = await conn.fetch(
                "SELECT id, external_task_id, status, downloaded_ok, downloaded_alt, "
                "(audio_url_ok IS NOT NULL AND audio_url_ok <> '') AS has_ok, "
                "(audio_url_alt IS NOT NULL AND audio_url_alt <> '') AS has_alt, created_at, updated_at "
                "FROM suno_tasks WHERE batch_id = $1 ORDER BY created_at LIMIT 20",
                batch_ids[0],
            )
            for t in tasks:
                print(json.dumps(dict(t), default=str))

        pending_all = await conn.fetchval(
            "SELECT COUNT(*) FROM suno_tasks st WHERE st.user_id = $1 AND st.status = 'success' "
            "AND ((st.audio_url_ok IS NOT NULL AND COALESCE(st.downloaded_ok, false) = false) "
            "OR (st.audio_url_alt IS NOT NULL AND COALESCE(st.downloaded_alt, false) = false))",
            uid,
        )
        pending_recent = await conn.fetchval(
            "SELECT COUNT(*) FROM suno_tasks st LEFT JOIN batches b ON b.id = st.batch_id "
            "WHERE st.user_id = $1 AND st.status = 'success' "
            "AND ((st.audio_url_ok IS NOT NULL AND COALESCE(st.downloaded_ok, false) = false) "
            "OR (st.audio_url_alt IS NOT NULL AND COALESCE(st.downloaded_alt, false) = false)) "
            "AND (b.id IS NULL OR b.updated_at >= NOW() - interval '30 days')",
            uid,
        )
        print(f"\\npending_all={pending_all} pending_recent_30d={pending_recent}")

        print("\\n=== Stream upload jobs (latest 15) ===")
        jobs = await conn.fetch(
            "SELECT id, kind, status, error, storage_key, suno_task_id, created_at "
            "FROM stream_upload_jobs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 15",
            uid,
        )
        for j in jobs:
            print(json.dumps(dict(j), default=str))

        print("\\n=== Stream tracks ===")
        tracks = await conn.fetch(
            "SELECT id, title, variant, publish_status, storage_key, created_at "
            "FROM stream_tracks WHERE user_id = $1 ORDER BY created_at DESC LIMIT 10",
            uid,
        )
        for t in tracks:
            print(json.dumps(dict(t), default=str))

        print("\\n=== Image jobs (latest batch) ===")
        if batch_ids:
            imgs = await conn.fetch(
                "SELECT id, kind, channel_role, status, error, provider, input_image_path, style_reference_path, output_image_path, updated_at "
                "FROM image_jobs WHERE batch_id = $1 ORDER BY created_at LIMIT 30",
                batch_ids[0],
            )
            if not imgs:
                print("(none - auto_gen_image may be off)")
            for img in imgs:
                d = dict(img)
                for key in ("output_image_path", "input_image_path", "style_reference_path"):
                    if d.get(key):
                        d[key] = str(d[key])[:120]
                print(json.dumps(d, default=str))
    finally:
        await conn.close()

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/diag_sommakara.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)

    print("\n=== API logs: Suno callback / streaming / image (last 6h) ===")
    log_cmd = (
        "journalctl -u camxora-api --since '6 hours ago' --no-pager | "
        "grep -iE 'Suno callback|streaming upload|MP3 streaming|schedule_suno|image job|IMAGE|callback.*suno' | tail -80"
    )
    _, log_out, _ = client.exec_command(log_cmd)
    print(log_out.read().decode("utf-8", errors="replace"))

    print("\n=== Callback env (masked) ===")
    _, env_out, _ = client.exec_command(
        "grep -E 'SUNO_CALLBACK' /opt/camxora/repo/platform_api/.env | sed 's/=.*$/=***/'"
    )
    print(env_out.read().decode("utf-8", errors="replace"))

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
