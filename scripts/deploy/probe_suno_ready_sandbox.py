#!/usr/bin/env python3
"""Extended sandbox probe for Suno readiness and stream pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r'''
import asyncio, asyncpg, json, os

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)

    print("=== Counts ===")
    for table in ("users", "batches", "songs", "suno_tasks", "stream_upload_jobs", "stream_tracks", "api_keys"):
        try:
            n = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {n}")
        except Exception as exc:
            print(f"{table}: ERR {exc}")

    print("\n=== Suno key pool ===")
    rows = await conn.fetch(
        "SELECT provider, status, COUNT(*) AS cnt FROM api_keys WHERE provider = 'suno' GROUP BY provider, status"
    )
    if not rows:
        print("(no suno keys)")
    for row in rows:
        print(dict(row))

    print("\n=== Recent batches ===")
    batches = await conn.fetch(
        "SELECT id, status, auto_gsuno, auto_gen_image, song_count, created_at FROM batches ORDER BY created_at DESC LIMIT 5"
    )
    for row in batches:
        print(json.dumps({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in dict(row).items()}, default=str))

    print("\n=== Suno env (redacted) ===")
    for key in (
        "PLATFORM_SUNO_CALLBACK_BASE_URL",
        "PLATFORM_SUNO_CALLBACK_HMAC_SECRET",
        "PLATFORM_SUNO_CALLBACK_ALLOWED_IPS",
        "PLATFORM_STREAMING_B2_BUCKET",
        "PLATFORM_STREAMING_CDN_BASE_URL",
    ):
        val = os.environ.get(key, "")
        if "SECRET" in key or "KEY" in key:
            val = "(set)" if val else "(missing)"
        print(f"{key}={val}")

    await conn.close()

asyncio.run(main())
'''

def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    path = "/tmp/probe_suno_ready.py"
    sftp = client.open_sftp()
    with sftp.file(path, "w") as f:
        f.write(REMOTE)
    sftp.close()
    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        f"set +a && /opt/camxora/repo/platform_api/.venv/bin/python {path}'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    sys.stdout.buffer.write(stdout.read())
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    client.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
