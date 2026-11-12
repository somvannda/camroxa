"""Seed one Suno pool key that routes generations to a local musicapi.

The platform picks the Suno base URL from the selected ``api_key_entries`` row, so a
key whose ``base_url`` is ``http://127.0.0.1:4003`` sends generations to ``musicapi``
(and its Suno web accounts) instead of sunoapi.org. The value is encrypted with the
same ``KeyEncryption`` the admin console uses, i.e. with the platform's
``PLATFORM_ENCRYPTION_MASTER_KEY``.

Usage (from the repo root):

    python scripts/dev/seed-local-suno-key.py --env-file "G:\\path\\to\\platform_api\\.env"

Then export the matching routing env before starting the stack::

    PLATFORM_SUNO_API_BASE_URL=http://127.0.0.1:4003
    PLATFORM_SUNO_CALLBACK_BASE_URL=https://<name>.trycloudflare.com

``musicapi`` rejects localhost callback URLs, so a public tunnel to :8100 is required
for the completion callback (see docs/studio/PROJECT_BLOCKERS.md, B-005).
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]

DEFAULT_KEY = "sk-test-123"
DEFAULT_BASE_URL = "http://127.0.0.1:4003"
DEFAULT_LABEL = "local musicapi"
DEFAULT_PRIORITY = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=os.environ.get("PLATFORM_ENV_FILE"),
        help="platform env file (default: $PLATFORM_ENV_FILE or platform_api/.env)",
    )
    parser.add_argument("--database-url", help="override PLATFORM_DATABASE_URL")
    parser.add_argument("--key", default=DEFAULT_KEY, help="musicapi API key to encrypt")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="musicapi base URL")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="pool row label")
    parser.add_argument("--priority", type=int, default=DEFAULT_PRIORITY)
    return parser.parse_args()


def resolve_env_file(raw: str | None) -> Path:
    if raw:
        path = Path(raw)
        if not path.exists():
            raise SystemExit(f"env file not found: {path}")
        return path
    candidate = REPO / "platform_api" / ".env"
    if candidate.exists():
        return candidate
    raise SystemExit(
        "No platform env file found. Pass --env-file or set PLATFORM_ENV_FILE."
    )


def asyncpg_dsn(raw: str) -> str:
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


async def main() -> None:
    args = parse_args()
    if args.priority < 1:
        raise SystemExit("--priority must be >= 1 (api_key_entries CHECK constraint)")

    env_file = resolve_env_file(args.env_file)
    load_dotenv(env_file)
    os.environ.setdefault("PLATFORM_ENV_FILE", str(env_file))

    sys.path.insert(0, str(REPO))
    import asyncpg
    from platform_api.config import get_settings
    from platform_api.services.key_encryption import KeyEncryption

    settings = get_settings()
    if not settings.encryption_master_key:
        raise SystemExit(
            f"PLATFORM_ENCRYPTION_MASTER_KEY is empty in {env_file}; "
            "the worker could not decrypt the key without it."
        )

    dsn = asyncpg_dsn(args.database_url or settings.database_url)
    encrypted = KeyEncryption(settings.encryption_master_key).encrypt(args.key)

    conn = await asyncpg.connect(dsn)
    try:
        existing = await conn.fetchval(
            "select id from api_key_entries where provider = 'suno' and label = $1",
            args.label,
        )
        if existing:
            await conn.execute(
                """
                update api_key_entries
                   set encrypted_key_value = $1, base_url = $2, priority = $3,
                       status = 'active', updated_at = now()
                 where id = $4
                """,
                encrypted,
                args.base_url,
                args.priority,
                existing,
            )
            entry_id = existing
            action = "updated"
        else:
            entry_id = await conn.fetchval(
                """
                insert into api_key_entries
                    (provider, label, encrypted_key_value, priority, status, base_url)
                values ('suno', $1, $2, $3, 'active', $4)
                returning id
                """,
                args.label,
                encrypted,
                args.priority,
                args.base_url,
            )
            action = "inserted"

        active = await conn.fetchval(
            "select count(*) from api_key_entries where provider = 'suno' and status = 'active'"
        )
    finally:
        await conn.close()

    print(f"{action} {entry_id} ({args.label} -> {args.base_url})")
    print(f"active suno pool keys: {active}")


if __name__ == "__main__":
    asyncio.run(main())
