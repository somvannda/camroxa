#!/usr/bin/env python3
"""Backfill missing Suno clip durations for web_music tasks (sandbox or production)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (
    ensure_deploy_key,
    load_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", choices=("sandbox", "production"), default="sandbox")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    secrets = load_secrets(args.env)
    if args.env == "production":
        host, user, password = resolve_production_ssh(secrets)
    else:
        host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    remote = rf"""
set -e
sudo -u camxora bash -lc "cd /opt/camxora/repo/platform_api && source .venv/bin/activate && export PYTHONPATH=/opt/camxora/repo && python - <<'PY'
import asyncio
import asyncpg
from platform_api.config import get_settings
from platform_api.services.suno_audio_resolver import poll_suno_generate_with_pool, urls_from_generate_poll

async def run() -> None:
    settings = get_settings()
    dsn = settings.database_url.replace('+asyncpg', '')
    pool = await asyncpg.create_pool(dsn)
    try:
        rows = await pool.fetch(
            '''
            SELECT id, external_task_id
            FROM suno_tasks
            WHERE source = 'web_music'
              AND UPPER(status) = 'SUCCESS'
              AND external_task_id IS NOT NULL
              AND (
                (duration_ok IS NULL AND COALESCE(audio_url_ok, b2_storage_key_ok) IS NOT NULL)
                OR (duration_alt IS NULL AND COALESCE(audio_url_alt, b2_storage_key_alt) IS NOT NULL)
              )
            ORDER BY updated_at DESC
            LIMIT {args.limit}
            '''
        )
        updated = 0
        for row in rows:
            external_id = str(row['external_task_id'] or '').strip()
            if not external_id:
                continue
            poll_result = await poll_suno_generate_with_pool(pool, external_id)
            if poll_result.state != 'success':
                continue
            urls = urls_from_generate_poll(poll_result)
            if urls.duration_ok is None and urls.duration_alt is None:
                continue
            await pool.execute(
                '''
                UPDATE suno_tasks
                SET duration_ok = COALESCE($2, duration_ok),
                    duration_alt = COALESCE($3, duration_alt),
                    updated_at = NOW()
                WHERE id = $1
                ''',
                row['id'],
                urls.duration_ok,
                urls.duration_alt,
            )
            updated += 1
        print(f'BACKFILL_UPDATED={{updated}}')
    finally:
        await pool.close()

asyncio.run(run())
PY"
"""
    _, stdout, _ = client.exec_command(remote, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    print(out.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
