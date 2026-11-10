#!/usr/bin/env python3
"""Seed the Creator Program sample discography into the catalog.

Reads ``docs/creator-program/sample-creators/discography.json`` and writes
``stream_albums``, ``stream_tracks`` and ``creator_releases`` rows for the
sample creator profiles (``creator_profiles.is_sample = true``).

Idempotent: re-running refreshes the sample rows instead of duplicating them.
Every row is tagged under the ``sample-creators/`` storage namespace and
``metadata.sample = "creator-program"`` so ``--remove`` can delete the whole
pack without touching real creators.

Never run this against production.

Usage:
    python scripts/creator-program/seed_sample_releases.py
    python scripts/creator-program/seed_sample_releases.py --remove
    python scripts/creator-program/seed_sample_releases.py --env-file G:/path/.env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOGRAPHY = (
    REPO_ROOT / "docs" / "creator-program" / "sample-creators" / "discography.json"
)
STORAGE_PREFIX = "sample-creators/"
SAMPLE_TAG = "creator-program"

AI_DISCLOSURE = {
    "original": "none",
    "ai_assisted": "ai_assisted",
    "ai_generated": "ai_artist",
}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def find_env_file(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise SystemExit(f"Env file not found: {path}")
        return path

    candidates = [
        REPO_ROOT / "platform_api" / ".env",
        REPO_ROOT.parent.parent / "Camxora" / "platform_api" / ".env",
        Path(r"G:\Developments\Projects\Camxora\platform_api\.env"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "Could not find platform_api/.env. Pass --env-file or set PLATFORM_DATABASE_URL."
    )


def normalize_dsn(dsn: str) -> str:
    return (
        dsn.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def database_url(env_file: Path) -> str:
    config = load_env_file(env_file)
    dsn = os.environ.get("PLATFORM_DATABASE_URL") or config.get("PLATFORM_DATABASE_URL")
    if not dsn:
        raise SystemExit("PLATFORM_DATABASE_URL is not configured.")
    return normalize_dsn(dsn)


def album_slug(album: dict[str, Any]) -> str:
    raw = str(album["id"])
    prefix = f"{album['creator_handle']}-"
    return raw[len(prefix):] if raw.startswith(prefix) else raw


def published_at(value: str | None) -> datetime:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


async def seed(conn: asyncpg.Connection, discography: dict[str, Any]) -> None:
    albums = discography["albums"]
    seeded_albums = 0
    seeded_tracks = 0
    skipped: list[str] = []

    for album in albums:
        handle = album["creator_handle"]
        profile = await conn.fetchrow(
            """
            SELECT user_id, ai_disclosure
            FROM creator_profiles
            WHERE handle = $1 AND is_sample = true AND status = 'active'
            """,
            handle,
        )
        if profile is None:
            skipped.append(handle)
            continue

        user_id = profile["user_id"]
        slug = album_slug(album)
        release_date = published_at(album.get("release_date"))
        genres = list(album.get("genres") or [album.get("genre")])

        album_id = await conn.fetchval(
            """
            INSERT INTO stream_albums (
                user_id, album_name, album_slug, channel_role,
                publish_status, published_at, genre, genres
            ) VALUES ($1,$2,$3,'ok','published',$4,$5,$6::jsonb)
            ON CONFLICT (user_id, album_slug) DO UPDATE SET
                album_name = EXCLUDED.album_name,
                publish_status = 'published',
                published_at = EXCLUDED.published_at,
                genre = EXCLUDED.genre,
                genres = EXCLUDED.genres,
                updated_at = NOW()
            RETURNING id
            """,
            user_id,
            album["title"],
            slug,
            release_date,
            album.get("genre"),
            json.dumps(genres),
        )

        # Replace the sample tracks for this album so re-runs stay idempotent.
        await conn.execute(
            "DELETE FROM stream_tracks WHERE album_id = $1 AND storage_key LIKE $2",
            album_id,
            f"{STORAGE_PREFIX}%",
        )

        track_ids: list[Any] = []
        for index, track in enumerate(album["tracks"], start=1):
            track_number = int(track.get("track_number") or index)
            title = track["title"]
            storage_key = f"{STORAGE_PREFIX}audio/{handle}/{slug}/{track_number:02d}.mp3"
            track_id = await conn.fetchval(
                """
                INSERT INTO stream_tracks (
                    user_id, album_id, title, lyrics, variant, storage_key,
                    duration_seconds, genre, genres, track_number,
                    publish_status, published_at, origin
                ) VALUES ($1,$2,$3,$4,'ok',$5,$6,$7,$8::jsonb,$9,'published',$10,$11)
                RETURNING id
                """,
                user_id,
                album_id,
                title,
                track.get("lyrics_km"),
                storage_key,
                track.get("duration_seconds"),
                album.get("genre"),
                json.dumps(genres),
                track_number,
                release_date,
                track.get("origin") or album.get("origin") or "ai_assisted",
            )
            track_ids.append(track_id)
            seeded_tracks += 1

        metadata = {
            "sample": SAMPLE_TAG,
            "sample_id": album["id"],
            "album_slug": slug,
            "prompt_id": album.get("prompt_id"),
            "language": album.get("language"),
            "release_type": album.get("release_type"),
        }
        ai_disclosure = AI_DISCLOSURE.get(
            str(album.get("origin") or "ai_assisted"), "ai_assisted"
        )
        existing = await conn.fetchval(
            """
            SELECT id FROM creator_releases
            WHERE creator_id = $1 AND metadata->>'sample_id' = $2
            """,
            user_id,
            album["id"],
        )
        if existing:
            await conn.execute(
                """
                UPDATE creator_releases
                SET album_id = $2, track_id = $3, status = 'published',
                    metadata = $4::jsonb, ai_disclosure = $5,
                    origin = $6, published_at = $7, updated_at = NOW()
                WHERE id = $1
                """,
                existing,
                album_id,
                track_ids[0] if track_ids else None,
                json.dumps(metadata),
                ai_disclosure,
                album.get("origin") or "ai_assisted",
                release_date,
            )
        else:
            await conn.execute(
                """
                INSERT INTO creator_releases (
                    creator_id, source_type, source_variant, album_id, track_id,
                    status, metadata, ai_disclosure, origin, published_at
                ) VALUES ($1,'upload','ok',$2,$3,'published',$4::jsonb,$5,$6,$7)
                """,
                user_id,
                album_id,
                track_ids[0] if track_ids else None,
                json.dumps(metadata),
                ai_disclosure,
                album.get("origin") or "ai_assisted",
                release_date,
            )
        seeded_albums += 1

    print(f"Seeded {seeded_albums} releases and {seeded_tracks} tracks.")
    if skipped:
        print(
            "Skipped (missing sample creator profile): " + ", ".join(sorted(set(skipped)))
        )


async def remove(conn: asyncpg.Connection) -> None:
    releases = await conn.execute(
        "DELETE FROM creator_releases WHERE metadata->>'sample' = $1",
        SAMPLE_TAG,
    )
    tracks = await conn.execute(
        "DELETE FROM stream_tracks WHERE storage_key LIKE $1",
        f"{STORAGE_PREFIX}%",
    )
    albums = await conn.execute(
        """
        DELETE FROM stream_albums a
        WHERE NOT EXISTS (
            SELECT 1 FROM stream_tracks t WHERE t.album_id = a.id
        )
          AND EXISTS (
            SELECT 1 FROM creator_profiles cp
            WHERE cp.user_id = a.user_id AND cp.is_sample = true
        )
        """
    )
    print(f"Removed sample rows: {releases}, {tracks}, {albums}.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to platform_api/.env")
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Delete the sample pack instead of seeding it.",
    )
    args = parser.parse_args()

    dsn = database_url(find_env_file(args.env_file))
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            if args.remove:
                await remove(conn)
            else:
                discography = json.loads(DISCOGRAPHY.read_text(encoding="utf-8"))
                await seed(conn, discography)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
