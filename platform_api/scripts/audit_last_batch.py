"""Audit the most recent batch: songs, rules, LLM calls, and billing."""

from __future__ import annotations

import asyncio
import json
import sys

import asyncpg

from platform_api.services.credit_units import units_to_credits
from platform_api.services.generation_service import (
    describe_draft_lyrics_validation_failure,
    describe_freeform_lyric_source_failure,
    extract_structure_header_lines,
    lyric_header_line,
    validate_lyrics_structure,
)


async def main(batch_id: str | None = None) -> None:
    conn = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/platform_db")
    try:
        if batch_id:
            batch = await conn.fetchrow(
                "SELECT id, song_count, status, created_at FROM batches WHERE id = $1::uuid",
                batch_id,
            )
        else:
            batch = await conn.fetchrow(
                "SELECT id, song_count, status, created_at FROM batches ORDER BY created_at DESC LIMIT 1"
            )
        if batch is None:
            print("No batch found")
            return

        batch_id = str(batch["id"])
        songs = await conn.fetch(
            """
            SELECT s.id, s.batch_index, s.title, s.album, s.status, s.lyrics,
                   d.name AS description_name, d.content AS description_content,
                   ms.name AS structure_name, ms.content AS structure_content
            FROM songs s
            LEFT JOIN music_descriptions d ON d.id = s.description_id
            LEFT JOIN music_structures ms ON ms.id = s.structure_id
            WHERE s.batch_id = $1::uuid
            ORDER BY s.batch_index
            """,
            batch_id,
        )

        txs = await conn.fetch(
            """
            SELECT amount, direction, reason, ref_id, metadata, created_at
            FROM credit_transactions
            WHERE metadata->>'batch_id' = $1
            ORDER BY created_at
            """,
            batch_id,
        )

        routing_raw = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = 'ai_routing_assignments'"
        )
        routing = json.loads(routing_raw) if isinstance(routing_raw, str) else (routing_raw or {})

        print(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "song_count": int(batch["song_count"]),
                    "batch_status": batch["status"],
                    "created_at": str(batch["created_at"]),
                    "routing": {
                        slot: routing.get(slot)
                        for slot in ("title", "album", "lyric", "music")
                        if routing.get(slot)
                    },
                },
                indent=2,
            )
        )

        total_debit = 0
        draft_debits: list[dict] = []
        for tx in txs:
            meta = tx["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            amount = int(tx["amount"])
            if tx["direction"] == "debit":
                total_debit += amount
            if tx["reason"] == "llm_draft" and tx["direction"] == "debit":
                draft_debits.append(
                    {
                        "batch_index": (meta or {}).get("batch_index"),
                        "amount_units": amount,
                        "amount_credits": units_to_credits(amount),
                        "llm_calls_title": (meta or {}).get("llm_calls_title"),
                        "llm_calls_album": (meta or {}).get("llm_calls_album"),
                        "llm_calls_lyric": (meta or {}).get("llm_calls_lyric"),
                        "attempts_used": (meta or {}).get("attempts_used"),
                        "line_items": (meta or {}).get("line_items"),
                        "status": (meta or {}).get("status"),
                    }
                )

        print("\n=== BILLING SUMMARY ===")
        print(json.dumps({"total_debit_units": total_debit, "total_debit_credits": units_to_credits(total_debit)}, indent=2))
        print("\n=== DRAFT DEBITS (per song) ===")
        for row in draft_debits:
            print(json.dumps(row, indent=2))

        print("\n=== PRICING ROWS (relevant) ===")
        pricing = await conn.fetch(
            """
            SELECT ai_service, operation_type, sub_model, credits_per_operation, needs_review
            FROM credit_pricing
            WHERE operation_type IN ('title', 'album', 'lyric')
            ORDER BY ai_service, operation_type, sub_model
            """
        )
        for row in pricing:
            print(json.dumps(dict(row), default=str))
        shared_album = songs[0]["album"] if songs else None
        for song in songs:
            headers = extract_structure_header_lines(song["structure_content"] or "")
            lyrics = song["lyrics"] or ""
            lines = [line for line in lyrics.splitlines() if line.strip()]
            content_lines = [line for line in lines if not line.strip().startswith("[")]
            unique_content = len(set(content_lines))
            print(
                json.dumps(
                    {
                        "batch_index": int(song["batch_index"]),
                        "song_id": str(song["id"]),
                        "title": song["title"],
                        "album": song["album"],
                        "shared_batch_album": song["album"] == shared_album,
                        "status": song["status"],
                        "description": song["description_name"],
                        "structure": song["structure_name"],
                        "lyrics_chars": len(lyrics),
                        "content_lines": len(content_lines),
                        "unique_content_lines": unique_content,
                        "structure_valid": validate_lyrics_structure(lyrics, headers),
                        "structure_issue": describe_draft_lyrics_validation_failure(lyrics, headers),
                        "expected_headers": [lyric_header_line(h) for h in headers],
                        "found_headers": [line for line in lines if line.strip().startswith("[")],
                    },
                    indent=2,
                )
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(arg))
