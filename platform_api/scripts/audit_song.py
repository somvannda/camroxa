"""One-off audit helper for a song row."""

from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

from platform_api.services.generation_service import (
    describe_draft_lyrics_validation_failure,
    extract_structure_header_lines,
    lyric_header_line,
    validate_lyrics_structure,
)


async def main(song_id: str) -> None:
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    row = await conn.fetchrow(
        """
        SELECT s.id, s.batch_id, s.batch_index, s.title, s.album, s.status, s.lyrics,
               d.name AS description_name, d.content AS description_content,
               ms.name AS structure_name, ms.content AS structure_content
        FROM songs s
        LEFT JOIN music_descriptions d ON d.id = s.description_id
        LEFT JOIN music_structures ms ON ms.id = s.structure_id
        WHERE s.id = $1::uuid
        """,
        song_id,
    )
    if row is None:
        print("Song not found")
        await conn.close()
        return

    headers = extract_structure_header_lines(row["structure_content"] or "")
    lyrics = row["lyrics"] or ""
    lines = [line for line in lyrics.splitlines() if line.strip()]
    content_lines = [line for line in lines if not line.strip().startswith("[")]

    print(json.dumps(
        {
            "song_id": str(row["id"]),
            "batch_id": str(row["batch_id"]),
            "batch_index": int(row["batch_index"]),
            "title": row["title"],
            "album": row["album"],
            "status": row["status"],
            "description_name": row["description_name"],
            "structure_name": row["structure_name"],
            "expected_headers": [lyric_header_line(header) for header in headers],
            "found_headers": [line for line in lines if line.strip().startswith("[")],
            "structure_valid": validate_lyrics_structure(lyrics, headers),
            "validation_message": describe_draft_lyrics_validation_failure(lyrics, headers),
            "content_line_count": len(content_lines),
            "unique_content_lines": len(set(content_lines)),
        },
        indent=2,
    ))

    txs = await conn.fetch(
        """
        SELECT amount, direction, reason, ref_id, metadata, created_at
        FROM credit_transactions
        WHERE ref_id = $1 OR metadata->>'song_id' = $1
        ORDER BY created_at
        """,
        song_id,
    )
    print("TRANSACTIONS")
    for tx in txs:
        metadata = tx["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        print(json.dumps(
            {
                "amount": int(tx["amount"]),
                "direction": tx["direction"],
                "reason": tx["reason"],
                "ref_id": tx["ref_id"],
                "llm_calls_title": (metadata or {}).get("llm_calls_title"),
                "llm_calls_album": (metadata or {}).get("llm_calls_album"),
                "llm_calls_lyric": (metadata or {}).get("llm_calls_lyric"),
                "attempts_used": (metadata or {}).get("attempts_used"),
                "status": (metadata or {}).get("status"),
                "line_items": (metadata or {}).get("line_items"),
                "created_at": str(tx["created_at"]),
            },
            indent=2,
        ))

    batch_id = str(row["batch_id"])
    siblings = await conn.fetch(
        """
        SELECT batch_index, title, album, status
        FROM songs
        WHERE batch_id = $1::uuid
        ORDER BY batch_index
        """,
        batch_id,
    )
    print("BATCH_SONGS")
    for sibling in siblings:
        print(dict(sibling))

    batch_txs = await conn.fetch(
        """
        SELECT metadata->>'batch_index' AS batch_index,
               metadata->>'llm_calls_title' AS llm_calls_title,
               metadata->>'llm_calls_album' AS llm_calls_album,
               metadata->>'llm_calls_lyric' AS llm_calls_lyric,
               amount, direction, reason
        FROM credit_transactions
        WHERE metadata->>'batch_id' = $1 AND reason = 'llm_draft'
        ORDER BY created_at
        """,
        batch_id,
    )
    print("BATCH_DRAFT_TX")
    for tx in batch_txs:
        print(dict(tx))

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "89bf5116-9d53-419b-b96c-01450c17f0d7"))
