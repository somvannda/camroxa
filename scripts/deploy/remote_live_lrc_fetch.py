#!/usr/bin/env python3
"""Run on VPS: fetch timestamped LRC for newest stream track."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path


def _load_dsn() -> str:
    for path in (
        Path("/opt/camxora/repo/platform_api/.env"),
        Path("/opt/camxora/repo/.env"),
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key in {"DATABASE_URL", "PLATFORM_DATABASE_URL"}:
                os.environ.setdefault(key, value)
                if key == "PLATFORM_DATABASE_URL" or "DATABASE_URL" not in os.environ:
                    os.environ.setdefault("DATABASE_URL", value)
                return value
    out = subprocess.check_output(
        ["systemctl", "show", "camxora-api", "-p", "EnvironmentFiles", "--value"],
        text=True,
    )
    raise SystemExit(f"no database url; envfiles={out.strip()!r}")


def _load_env() -> str:
    dsn = ""
    for path in (
        Path("/opt/camxora/repo/platform_api/.env"),
        Path("/opt/camxora/repo/.env"),
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)
            if key in {"DATABASE_URL", "PLATFORM_DATABASE_URL"} and not dsn:
                dsn = value
    if not dsn:
        raise SystemExit("no database url")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn.split("://", 1)[1]
    return dsn


async def main() -> None:
    import asyncpg
    from platform_api.services.suno_audio_resolver import fetch_timestamped_lrc_with_pool
    from platform_api.services.suno_lrc import looks_like_lrc
    from platform_api.services.suno_audio_resolver import _suno_client_with_pool_key

    dsn = _load_env()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    row = await pool.fetchrow(
        """
        SELECT st.title, st.suno_audio_id, t.external_task_id
        FROM stream_tracks st
        JOIN suno_tasks t ON t.id = st.suno_task_id
        WHERE st.suno_audio_id IS NOT NULL AND st.suno_audio_id <> ''
          AND t.external_task_id IS NOT NULL
        ORDER BY st.created_at DESC
        LIMIT 1
        """
    )
    print("TRACK", row["title"])
    print("AUDIO", row["suno_audio_id"])
    print("TASK", row["external_task_id"])

    client, api_key = await _suno_client_with_pool_key(pool)
    raw = await client.get_timestamped_lyrics(
        task_id=str(row["external_task_id"]),
        audio_id=str(row["suno_audio_id"]),
        api_key=api_key,
    )
    print("RAW_CODE", raw.get("code"))
    print("RAW_MSG", str(raw.get("msg") or "")[:200])
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    print("DATA_KEYS", sorted(list(data.keys()))[:30] if isinstance(data, dict) else type(data))
    words = data.get("alignedWords") or data.get("aligned_words") if isinstance(data, dict) else None
    print("WORDS_N", len(words) if isinstance(words, list) else None)
    if isinstance(words, list) and words:
        print("WORD0", words[0])

    lrc = await fetch_timestamped_lrc_with_pool(
        pool,
        external_task_id=str(row["external_task_id"]),
        audio_id=str(row["suno_audio_id"]),
    )
    print("LRC_LEN", len(lrc or ""))
    print("IS_LRC", looks_like_lrc(lrc))
    print("HEAD", (lrc or "")[:400].replace("\n", " | "))
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
