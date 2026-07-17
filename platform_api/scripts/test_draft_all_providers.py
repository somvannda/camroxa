"""Smoke-test split draft generation across all registered text providers/models.

Usage (from platform_api/):
    python scripts/test_draft_all_providers.py

Requires a running database, Redis, and active API keys in the key pool.
Uses skip_pricing=True so no credits are deducted.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def bootstrap_runtime() -> None:
    import asyncpg
    import redis.asyncio as aioredis

    from platform_api.config import get_settings
    from platform_api.dependencies import set_db_pool, set_redis

    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    redis_conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    set_db_pool(pool)
    set_redis(redis_conn)

    if settings.encryption_master_key:
        from platform_api.repositories.key_pool_repo import KeyPoolRepository
        from platform_api.services.key_encryption import KeyEncryption
        from platform_api.services.key_pool_service import KeyPoolService

        key_pool = KeyPoolService(
            repository=KeyPoolRepository(pool=pool),
            encryption=KeyEncryption(master_key=settings.encryption_master_key),
            redis=redis_conn,
        )
        await key_pool.load_all_caches()


async def shutdown_runtime() -> None:
    from platform_api.dependencies import clear_connections, get_db_pool, get_redis

    redis_conn = get_redis()
    pool = get_db_pool()
    if redis_conn is not None:
        await redis_conn.aclose()
    if pool is not None:
        await pool.close()
    clear_connections()


async def main() -> int:
    await bootstrap_runtime()

    from platform_api.ai.purposes.draft_routing import build_draft_routing
    from platform_api.ai.registry import TEXT_MODEL_REGISTRY
    from platform_api.dependencies import get_generation_service, get_key_pool_service
    from platform_api.ports.generation_port import DraftRequest
    from platform_api.services.generation_service import (
        describe_structure_validation_failure,
        extract_structure_header_lines,
    )

    service = get_generation_service()
    key_pool = get_key_pool_service()

    structure = "\n".join(
        [
            "[Intro: short synth build]",
            "[Verse: energetic groove]",
            "[Chorus: anthemic hook]",
            "[Outro: fade]",
        ]
    )
    structure_headers = extract_structure_header_lines(structure)
    request = DraftRequest(
        language="en",
        creativity_level=45,
        description="EDM workout gym track with driving bass",
        structure=structure,
    )

    print("=" * 72)
    print("DRAFT GENERATION SMOKE TEST — all registered text providers/models")
    print("=" * 72)

    rows: list[tuple[str, str, str, str, float]] = []
    failures = 0
    skipped = 0
    passed = 0

    for provider, models in TEXT_MODEL_REGISTRY.items():
        pool_status = await key_pool.get_pool_status(provider)
        active_keys = int(pool_status.get("active_keys") or 0)
        if active_keys < 1:
            rows.append((provider, "*", "SKIP", "no active API keys in pool", 0.0))
            skipped += 1
            continue

        for model_id in models:
            routing = build_draft_routing(
                type(
                    "R",
                    (),
                    {"provider": provider, "sub_model": model_id},
                )()
            )
            started = time.perf_counter()
            try:
                draft = await service.submit_draft(
                    "00000000-0000-0000-0000-000000000001",
                    request,
                    provider=provider,
                    model=model_id,
                    draft_routing=routing,
                    skip_pricing=True,
                )
                elapsed = time.perf_counter() - started
                structure_failure = describe_structure_validation_failure(
                    draft.lyrics, structure_headers
                )
                if structure_failure is not None:
                    rows.append((provider, model_id, "FAIL", structure_failure[:100], elapsed))
                    failures += 1
                elif not draft.title or not draft.album or not draft.lyrics:
                    rows.append((provider, model_id, "FAIL", "empty title/album/lyrics", elapsed))
                    failures += 1
                else:
                    rows.append(
                        (
                            provider,
                            model_id,
                            "PASS",
                            f"'{draft.title[:40]}' / '{draft.album[:30]}'",
                            elapsed,
                        )
                    )
                    passed += 1
            except Exception as exc:
                elapsed = time.perf_counter() - started
                rows.append((provider, model_id, "FAIL", str(exc)[:100], elapsed))
                failures += 1

    for provider, model_id, status, detail, elapsed in rows:
        timing = f"{elapsed:6.1f}s" if elapsed else "      "
        print(f"{status:4}  {timing}  {provider:10}  {model_id:24}  {detail}")

    print("-" * 72)
    print(f"Passed: {passed}  Failed: {failures}  Skipped: {skipped}")
    print("=" * 72)

    await shutdown_runtime()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
