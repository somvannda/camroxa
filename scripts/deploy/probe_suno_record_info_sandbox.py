#!/usr/bin/env python3
"""Poll Suno record-info and compare download URLs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r'''
import asyncio
import json
import os
import asyncpg
import httpx

from platform_api.clients.suno_client import parse_suno_generate_poll, _extract_clip_audio_url, _iter_generate_clips

async def head(client, url):
    if not url:
        return None
    try:
        r = await client.get(url, follow_redirects=True)
        return {"status": r.status_code, "len": len(r.content), "type": r.headers.get("content-type"), "url": url[:140]}
    except Exception as exc:
        return {"error": str(exc)[:120], "url": url[:140]}

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        "SELECT external_task_id, audio_url_ok, audio_url_alt FROM suno_tasks "
        "WHERE batch_id = '6ba527b6-01f1-4a5e-91a4-c9d0daaeaad2' LIMIT 1"
    )
    key = await conn.fetchval("SELECT api_key FROM api_key_entries WHERE provider='suno' AND status='active' LIMIT 1")
    await conn.close()
    if not row or not key:
        print("missing row or key")
        return
    ext = row["external_task_id"]
    base = os.environ.get("PLATFORM_SUNO_API_BASE_URL", "https://musicapi.camxora.com").rstrip("/")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{base}/api/v1/generate/record-info",
            params={"taskId": ext},
            headers={"Authorization": f"Bearer {key}"},
        )
        print("record-info status", resp.status_code)
        payload = resp.json()
        parsed = parse_suno_generate_poll(payload)
        print("parsed", parsed)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        clips = _iter_generate_clips(data)
        print("clip count", len(clips))
        for i, clip in enumerate(clips):
            print(f"clip {i} keys", sorted(clip.keys()))
            for k in ("source_audio_url","sourceAudioUrl","audio_url","audioUrl","stream_audio_url","streamAudioUrl"):
                if clip.get(k):
                    print(f"  {k}:", str(clip.get(k))[:140])
            print(f"  pick:", _extract_clip_audio_url(clip)[:140])
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Camxora/1.0)", "Accept": "*/*"}
        async with httpx.AsyncClient(timeout=60.0, headers=headers) as dl:
            print("stored ok", await head(dl, row["audio_url_ok"]))
            print("stored alt", await head(dl, row["audio_url_alt"]))
            if parsed.audio_url_ok:
                print("fresh ok", await head(dl, parsed.audio_url_ok))
            if parsed.audio_url_alt:
                print("fresh alt", await head(dl, parsed.audio_url_alt))
            for i, clip in enumerate(clips):
                for k in ("source_audio_url","sourceAudioUrl","audio_url","audioUrl"):
                    u = str(clip.get(k) or "").strip()
                    if u:
                        print(f"head clip{i} {k}", await head(dl, u))

asyncio.run(main())
'''


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/probe_suno_record.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        f"set +a && PYTHONPATH=/opt/camxora/repo platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
