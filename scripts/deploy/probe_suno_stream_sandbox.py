#!/usr/bin/env python3
"""Probe sandbox Suno -> music stream upload pipeline."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE_SCRIPT = '''
import asyncio, asyncpg, json, os

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)

    print("=== Streaming config (system_settings) ===")
    rows = await conn.fetch(
        "SELECT key, value FROM system_settings WHERE key LIKE 'streaming.%' ORDER BY key"
    )
    for row in rows:
        key = row["key"]
        val = row["value"]
        if "application_key" in key:
            val = "(encrypted)" if val else "(missing)"
        print(f"{key}: {val}")

    print("\\n=== Recent Suno tasks (last 8) ===")
    tasks = await conn.fetch(
        "SELECT st.id, st.external_task_id, st.status, st.created_at, st.updated_at, "
        "(st.audio_url_ok IS NOT NULL AND st.audio_url_ok <> '') AS has_ok_url, "
        "(st.audio_url_alt IS NOT NULL AND st.audio_url_alt <> '') AS has_alt_url, "
        "st.downloaded_ok, st.downloaded_alt, b.auto_gsuno, s.title AS song_title "
        "FROM suno_tasks st "
        "LEFT JOIN songs s ON s.id = st.song_id "
        "LEFT JOIN batches b ON b.id = st.batch_id "
        "ORDER BY st.created_at DESC LIMIT 8"
    )
    for row in tasks:
        print(json.dumps({
            "id": str(row["id"]),
            "external_task_id": row["external_task_id"],
            "status": row["status"],
            "song_title": row["song_title"],
            "auto_gsuno": row["auto_gsuno"],
            "has_ok_url": row["has_ok_url"],
            "has_alt_url": row["has_alt_url"],
            "downloaded_ok": row["downloaded_ok"],
            "downloaded_alt": row["downloaded_alt"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }, default=str))

    print("\\n=== Recent stream upload jobs (last 12) ===")
    jobs = await conn.fetch(
        "SELECT id, kind, status, storage_key, error, source_url, suno_task_id, created_at, updated_at "
        "FROM stream_upload_jobs ORDER BY created_at DESC LIMIT 12"
    )
    if not jobs:
        print("(none)")
    for row in jobs:
        print(json.dumps({
            "id": str(row["id"]),
            "kind": row["kind"],
            "status": row["status"],
            "storage_key": row["storage_key"],
            "error": row["error"],
            "source_url": (row["source_url"] or "")[:80],
            "suno_task_id": str(row["suno_task_id"]) if row["suno_task_id"] else None,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }, default=str))

    print("\\n=== Recent published stream tracks (last 8) ===")
    tracks = await conn.fetch(
        "SELECT t.id, t.title, t.variant, t.storage_key, t.publish_status, t.created_at, "
        "a.album_name, a.album_slug "
        "FROM stream_tracks t JOIN stream_albums a ON a.id = t.album_id "
        "ORDER BY t.created_at DESC LIMIT 8"
    )
    if not tracks:
        print("(none)")
    for row in tracks:
        print(json.dumps({
            "id": str(row["id"]),
            "title": row["title"],
            "variant": row["variant"],
            "album": row["album_name"],
            "storage_key": row["storage_key"],
            "publish_status": row["publish_status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }, default=str))

    print("\\n=== SUCCESS tasks missing any stream upload job ===")
    missing = await conn.fetch(
        "SELECT st.id, st.status, st.created_at, s.title "
        "FROM suno_tasks st LEFT JOIN songs s ON s.id = st.song_id "
        "WHERE st.status = 'SUCCESS' AND ("
        "(st.audio_url_ok IS NOT NULL AND st.audio_url_ok <> '') OR "
        "(st.audio_url_alt IS NOT NULL AND st.audio_url_alt <> '')) "
        "AND NOT EXISTS (SELECT 1 FROM stream_upload_jobs j WHERE j.suno_task_id = st.id) "
        "ORDER BY st.created_at DESC LIMIT 10"
    )
    if not missing:
        print("(none)")
    for row in missing:
        print(json.dumps({
            "suno_task_id": str(row["id"]),
            "title": row["title"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }, default=str))

    await conn.close()

asyncio.run(main())
'''


def probe_public_api() -> None:
    print("\n=== Public streaming API ===")
    for url in (
        "https://api.sandbox.camxora.com/api/v1/public/streaming/home",
        "https://music.sandbox.camxora.com",
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "camxora-probe/1.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read(8000).decode("utf-8", errors="replace")
                print(f"{url} -> {resp.status}")
                if "streaming/home" in url:
                    try:
                        data = json.loads(body)
                        featured = data.get("featured_tracks") or data.get("tracks") or []
                        print(f"  featured_tracks: {len(featured)}")
                        if featured:
                            print(f"  latest: {featured[0].get('title')} ({featured[0].get('id')})")
                    except json.JSONDecodeError:
                        print(body[:300])
        except urllib.error.HTTPError as exc:
            print(f"{url} -> HTTP {exc.code} {exc.read(200).decode()[:200]}")
        except Exception as exc:
            print(f"{url} -> ERR {type(exc).__name__}: {exc}")


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    remote_path = "/tmp/probe_suno_stream.py"
    sftp = client.open_sftp()
    with sftp.file(remote_path, "w") as remote_file:
        remote_file.write(REMOTE_SCRIPT)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        f"set +a && /opt/camxora/repo/platform_api/.venv/bin/python {remote_path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(b"\nSTDERR:\n")
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))

    print("\n=== Recent API logs (suno callback / streaming upload) ===")
    log_cmd = (
        "journalctl -u camxora-api -n 400 --no-pager | "
        "grep -iE 'Suno callback|streaming upload|MP3 streaming|stream_upload|schedule_suno' | tail -25"
    )
    _, log_out, _ = client.exec_command(log_cmd)
    sys.stdout.buffer.write(log_out.read())

    client.close()
    probe_public_api()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
