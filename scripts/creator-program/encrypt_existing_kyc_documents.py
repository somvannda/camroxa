#!/usr/bin/env python3
"""Encrypt KYC documents that were stored before encryption existed.

Rows written before migration 195 have ``documents_encrypted = false`` and the
object in the bucket is the raw image or PDF. This script downloads each one,
encrypts it, writes the ciphertext back to the same key, and marks the row.

Idempotent: a document that is already ciphertext is skipped.

Usage:
    python scripts/creator-program/encrypt_existing_kyc_documents.py --dry-run
    python scripts/creator-program/encrypt_existing_kyc_documents.py
    python scripts/creator-program/encrypt_existing_kyc_documents.py --env-file G:/path/.env
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from platform_api.services.document_encryption import DocumentCipher  # noqa: E402
from platform_api.services.storage_service import StorageService  # noqa: E402
from platform_api.services.streaming_config_service import (  # noqa: E402
    resolve_streaming_storage_config,
)

EXTENSION_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".pdf": "application/pdf",
}


class _PoolAdapter:
    """Minimal asyncpg pool surface for the storage config resolver."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetchrow(self, *args, **kwargs):
        return await self._pool.fetchrow(*args, **kwargs)

    async def fetchval(self, *args, **kwargs):
        return await self._pool.fetchval(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        return await self._pool.fetch(*args, **kwargs)

    async def execute(self, *args, **kwargs):
        return await self._pool.execute(*args, **kwargs)


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
    for candidate in (
        REPO_ROOT / "platform_api" / ".env",
        Path(r"G:\Developments\Projects\Camxora\platform_api\.env"),
    ):
        if candidate.exists():
            return candidate
    raise SystemExit("Could not find platform_api/.env. Pass --env-file.")


def normalize_dsn(dsn: str) -> str:
    return (
        dsn.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def media_type_for(key: str) -> str:
    return EXTENSION_TYPES.get(Path(key).suffix.lower(), "application/octet-stream")


def looks_like_ciphertext(blob: bytes) -> bool:
    # PNG, JPEG and PDF all have distinct magic bytes; ciphertext starts with 0x01.
    return DocumentCipher.is_encrypted(blob)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", help="Path to platform_api/.env")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    env_file = find_env_file(args.env_file)
    config = load_env_file(env_file)
    dsn = config.get("PLATFORM_DATABASE_URL")
    master = config.get("PLATFORM_ENCRYPTION_MASTER_KEY")
    if not dsn:
        raise SystemExit("PLATFORM_DATABASE_URL is not configured.")
    if not master:
        raise SystemExit("PLATFORM_ENCRYPTION_MASTER_KEY is not configured.")

    pool = await asyncpg.create_pool(normalize_dsn(dsn), min_size=1, max_size=2)
    try:
        storage_config = await resolve_streaming_storage_config(_PoolAdapter(pool))
        if not storage_config.configured:
            raise SystemExit("Storage is not configured; nothing to do.")
        storage = StorageService.from_config(storage_config)
        cipher = DocumentCipher(master)

        rows = await pool.fetch(
            """
            SELECT user_id, id_document_ref, selfie_ref
            FROM creator_kyc
            WHERE COALESCE(documents_encrypted, false) = false
            """
        )
        print(f"rows to inspect: {len(rows)}")
        converted = 0
        skipped = 0
        failed = 0

        for row in rows:
            refs = [row["id_document_ref"], row["selfie_ref"]]
            targets = [r for r in refs if r and not str(r).lower().startswith(("http://", "https://"))]
            for key in targets:
                try:
                    blob = await storage.download_bytes(key)
                except Exception as exc:
                    print(f"  ! cannot read {key}: {exc}")
                    failed += 1
                    continue
                if looks_like_ciphertext(blob):
                    skipped += 1
                    continue
                if args.dry_run:
                    print(f"  would encrypt {key} ({len(blob)} bytes)")
                    converted += 1
                    continue
                await storage.upload_bytes(
                    key=key,
                    data=cipher.encrypt(blob),
                    content_type="application/octet-stream",
                )
                print(f"  encrypted {key}")
                converted += 1

            if not args.dry_run and targets:
                await pool.execute(
                    """
                    UPDATE creator_kyc
                    SET documents_encrypted = true,
                        id_document_type = COALESCE(id_document_type, $2),
                        selfie_type = COALESCE(selfie_type, $3)
                    WHERE user_id = $1
                    """,
                    row["user_id"],
                    media_type_for(str(row["id_document_ref"] or "")),
                    media_type_for(str(row["selfie_ref"] or "")) if row["selfie_ref"] else None,
                )

        print(
            f"done: converted={converted} already_encrypted={skipped} failed={failed}"
            + (" (dry run)" if args.dry_run else "")
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
