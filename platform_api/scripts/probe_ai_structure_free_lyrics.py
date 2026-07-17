"""Probe lyric AI providers/models without structure templates.

Runs description-only prompts and records how each provider formats lyrics.
Use results to tune AI Structure acceptance rules.

Usage (from repo root):
    cd platform_api && python scripts/probe_ai_structure_free_lyrics.py

Optional:
    python scripts/probe_ai_structure_free_lyrics.py --output ../docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


TEST_DESCRIPTIONS = [
    "EDM workout gym track with driving bass, energetic drops, and motivational lyrics",
    "Lo-fi chill study beat with warm piano, soft drums, and reflective mood",
]

RUNS_PER_MODEL = 2


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


async def probe_chat_provider(
    *,
    gateway: Any,
    key_pool: Any,
    provider: str,
    model_id: str,
    description: str,
    run_index: int,
) -> dict[str, Any]:
    from platform_api.ai.types import is_suno_lyric_routing
    from platform_api.services.generation_service import (
        STRUCTURE_MODE_AI_FREE,
        analyze_ai_structure_lyric_response,
        build_ai_structure_lyrics_system_prompt,
        build_ai_structure_lyrics_user_prompt,
        build_suno_lyrics_prompt,
        describe_ai_structure_validation_failure,
        normalize_ai_structure_lyrics,
        parse_plain_lyric_text,
    )

    started = time.perf_counter()
    try:
        if is_suno_lyric_routing(provider=provider, operation="lyric") and model_id == "lyrics":
            from platform_api.dependencies import get_generation_service

            prompt = build_suno_lyrics_prompt(
                description=description,
                structure="",
                language="en",
                structure_mode=STRUCTURE_MODE_AI_FREE,
            )
            service = get_generation_service()
            raw = await service._call_suno_lyrics(prompt=prompt)
        else:
            system_prompt = build_ai_structure_lyrics_system_prompt(language="en")
            user_prompt = build_ai_structure_lyrics_user_prompt(description=description)
            raw = await gateway.generate_text(
                provider=provider,
                model=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.55,
                max_tokens=2048,
                prefer_json=False,
            )
            raw = parse_plain_lyric_text(raw)

        normalized = normalize_ai_structure_lyrics(raw)
        analysis = analyze_ai_structure_lyric_response(raw)
        validation_error = describe_ai_structure_validation_failure(normalized)
        elapsed = time.perf_counter() - started
        return {
            "provider": provider,
            "model": model_id,
            "run": run_index,
            "description": description[:80],
            "status": "PASS" if validation_error is None else "FAIL",
            "validation_error": validation_error,
            "elapsed_seconds": round(elapsed, 2),
            "analysis": analysis,
            "raw_preview": str(raw or "")[:800],
            "normalized_preview": normalized[:800],
        }
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return {
            "provider": provider,
            "model": model_id,
            "run": run_index,
            "description": description[:80],
            "status": "ERROR",
            "validation_error": str(exc)[:300],
            "elapsed_seconds": round(elapsed, 2),
            "analysis": {},
            "raw_preview": "",
            "normalized_preview": "",
        }


async def main() -> int:
    import os

    # Broken PLATFORM_CORS_ORIGINS placeholders in .env must not override defaults.
    os.environ.pop("PLATFORM_CORS_ORIGINS", None)

    parser = argparse.ArgumentParser(description="Probe AI Structure Free lyric providers")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "AI_STRUCTURE_FREE_PROVIDER_PROBE.json"),
        help="JSON output path for probe results",
    )
    args = parser.parse_args()

    await bootstrap_runtime()

    from platform_api.ai.registry import TEXT_MODEL_REGISTRY
    from platform_api.dependencies import get_generation_service, get_key_pool_service

    key_pool = get_key_pool_service()
    gateway = get_generation_service()._get_text_gateway()

    results: list[dict[str, Any]] = []
    print("=" * 80)
    print("AI STRUCTURE FREE — provider probe (no structure template)")
    print("=" * 80)

    for provider, models in TEXT_MODEL_REGISTRY.items():
        pool_status = await key_pool.get_pool_status(provider)
        active_keys = int(pool_status.get("active_keys") or 0)
        if active_keys < 1:
            print(f"SKIP  {provider:10}  no active API keys")
            continue

        for model_id in models:
            for run_index in range(1, RUNS_PER_MODEL + 1):
                description = TEST_DESCRIPTIONS[(run_index - 1) % len(TEST_DESCRIPTIONS)]
                row = await probe_chat_provider(
                    gateway=gateway,
                    key_pool=key_pool,
                    provider=provider,
                    model_id=model_id,
                    description=description,
                    run_index=run_index,
                )
                results.append(row)
                status = row["status"]
                detail = row.get("validation_error") or (
                    f"headers={row['analysis'].get('header_count', 0)} "
                    f"lines={row['analysis'].get('content_line_count', 0)}"
                )
                print(
                    f"{status:5}  {row['elapsed_seconds']:5.1f}s  "
                    f"{provider:10}  {model_id:24}  run={run_index}  {str(detail)[:80]}"
                )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs_per_model": RUNS_PER_MODEL,
        "test_descriptions": TEST_DESCRIPTIONS,
        "results": results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("-" * 80)
    print(f"Wrote {len(results)} probe rows to {output_path}")

    await shutdown_runtime()
    failures = sum(1 for row in results if row["status"] != "PASS")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
