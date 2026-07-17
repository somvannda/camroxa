"""Audit the last N songs across recent batches."""

from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

from platform_api.services.credit_units import units_to_credits
from platform_api.services.generation_service import (
    describe_draft_lyrics_validation_failure,
    extract_structure_header_lines,
    validate_lyrics_structure,
)


async def main(limit: int = 10) -> None:
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    try:
        songs = await conn.fetch(
            """
            SELECT s.id, s.batch_id, s.batch_index, s.title, s.album, s.status, s.lyrics,
                   s.created_at, s.updated_at,
                   b.language, b.secondary_language, b.status AS batch_status, b.created_at AS batch_created_at,
                   d.name AS description_name, d.vocal_profile,
                   ms.name AS structure_name
            FROM songs s
            JOIN batches b ON b.id = s.batch_id
            LEFT JOIN music_descriptions d ON d.id = s.description_id
            LEFT JOIN music_structures ms ON ms.id = s.structure_id
            ORDER BY s.created_at DESC
            LIMIT $1
            """,
            limit,
        )

        print(f"=== LAST {limit} SONGS (newest first) ===\n")
        for song in songs:
            headers = extract_structure_header_lines(song["structure_name"] or "")
            lyrics = song["lyrics"] or ""
            lines = [line for line in lyrics.splitlines() if line.strip()]
            content_lines = [line for line in lines if not line.strip().startswith("[")]
            vocal_profile = song["vocal_profile"]
            if isinstance(vocal_profile, str):
                try:
                    vocal_profile = json.loads(vocal_profile)
                except json.JSONDecodeError:
                    vocal_profile = None

            draft_tx = await conn.fetchrow(
                """
                SELECT amount, metadata, created_at
                FROM credit_transactions
                WHERE reason = 'llm_draft'
                  AND ref_id = $1
                  AND direction = 'debit'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                str(song["id"]),
            )
            meta = {}
            if draft_tx and draft_tx["metadata"]:
                meta = draft_tx["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)

            print(
                json.dumps(
                    {
                        "song_id": str(song["id"])[:8],
                        "batch_id": str(song["batch_id"])[:8],
                        "index": int(song["batch_index"]),
                        "status": song["status"],
                        "batch_status": song["batch_status"],
                        "description": song["description_name"],
                        "structure": song["structure_name"],
                        "batch_language": song["language"],
                        "batch_secondary_language": song["secondary_language"],
                        "vocal_profile": vocal_profile,
                        "title": song["title"],
                        "album": song["album"],
                        "lyrics_chars": len(lyrics),
                        "content_lines": len(content_lines),
                        "structure_valid": validate_lyrics_structure(lyrics, headers) if headers else None,
                        "structure_issue": describe_draft_lyrics_validation_failure(lyrics, headers) if headers else None,
                        "llm_calls": {
                            "title": meta.get("llm_calls_title"),
                            "album": meta.get("llm_calls_album"),
                            "lyric": meta.get("llm_calls_lyric"),
                            "attempts": meta.get("attempts_used"),
                        },
                        "draft_credits": units_to_credits(int(draft_tx["amount"])) if draft_tx else None,
                        "created_at": str(song["created_at"]),
                    },
                    indent=2,
                )
            )
            print()
    finally:
        await conn.close()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(main(n))
