"""Probe lyric AI providers/models without structure templates.

Runs description-only prompts and records how each provider formats lyrics.
Use results to tune AI Structure acceptance rules.

Usage (from repo root):
    cd platform_api && python scripts/probe_ai_structure_free_lyrics.py

Optional:
    python scripts/probe_ai_structure_free_lyrics.py --output ../docs/AI_STRUCTURE_FREE_PROVIDER_PROBE.json
    python scripts/probe_ai_structure_free_lyrics.py --runs 3 --lyrics-dir ../docs/ai_free_probe_lyrics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
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
    "Pop ballad about long-distance love, emotional vocals, piano and strings",
]

DEFAULT_RUNS_PER_MODEL = 3

# Patterns that should never appear in final normalized lyrics (manual review).
_META_GARBAGE_RE = re.compile(
    r"(^---+$|^\*\*.*\*\*$|"
    r"\b(boat block|end mark|remaining through|audio void|do not repeat dropped|"
    r"only low noise|ok cut|aus fade|silence shorter|au revoir|production note|"
    r"fade to silence|cut to black)\b)",
    re.IGNORECASE,
)
# Truncation hints — exclude ellipses (common in outros) and section headers.
_TRUNCATION_TAIL_RE = re.compile(r"(,\s*$|;\s*$|\band\s*$|\bthe\s*$|\bto\s*$)", re.IGNORECASE)
_NON_LATIN_RE = re.compile(r"[\u0600-\u06FF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0400-\u04FF]")


def manual_lyric_review(
    *,
    raw: str,
    normalized: str,
    language: str = "en",
) -> list[str]:
    """Human-oriented quality checks beyond automated validation."""
    issues: list[str] = []
    raw_text = str(raw or "")
    norm_text = str(normalized or "").strip()

    for line in norm_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _META_GARBAGE_RE.search(stripped):
            issues.append(f"meta_garbage: {stripped[:80]}")
            break

    if raw_text and norm_text and len(norm_text) < len(raw_text) * 0.85:
        issues.append("normalization_removed_large_tail")

    content_lines = [
        line.strip()
        for line in norm_text.splitlines()
        if line.strip() and not line.strip().startswith("[")
    ]
    if content_lines:
        last_line = content_lines[-1]
        if _TRUNCATION_TAIL_RE.search(last_line):
            issues.append(f"possible_truncation: last line ends abruptly ({last_line[:60]})")
        elif last_line.endswith("...") and not last_line.endswith("...."):
            issues.append(f"possible_truncation: last line ends with ellipsis ({last_line[:60]})")

    if language.lower() in {"en", "english"}:
        non_latin = [
            line.strip()
            for line in content_lines
            if _NON_LATIN_RE.search(line)
        ]
        if non_latin:
            issues.append(f"mixed_language: {len(non_latin)} non-Latin lines in English run")

    header_lines = [line for line in norm_text.splitlines() if line.strip().startswith("[")]
    if not header_lines:
        issues.append("missing_section_headers")

    if len(content_lines) < 16:
        issues.append(f"short_song: only {len(content_lines)} content lines")

    return issues


def _safe_filename(provider: str, model_id: str, run_index: int, suffix: str) -> str:
    model_slug = re.sub(r"[^\w.-]+", "_", model_id)
    return f"{provider}_{model_slug}_run{run_index}_{suffix}.txt"


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
    provider: str,
    model_id: str,
    description: str,
    run_index: int,
    lyrics_dir: Path | None,
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
        review_issues = manual_lyric_review(raw=raw, normalized=normalized, language="en")
        elapsed = time.perf_counter() - started

        lyric_file: str | None = None
        if lyrics_dir is not None:
            lyrics_dir.mkdir(parents=True, exist_ok=True)
            lyric_path = lyrics_dir / _safe_filename(provider, model_id, run_index, "normalized")
            lyric_path.write_text(normalized, encoding="utf-8")
            raw_path = lyrics_dir / _safe_filename(provider, model_id, run_index, "raw")
            raw_path.write_text(str(raw or ""), encoding="utf-8")
            lyric_file = str(lyric_path.relative_to(REPO_ROOT))

        status = "PASS"
        if validation_error is not None:
            status = "FAIL"
        elif review_issues:
            status = "WARN"

        return {
            "provider": provider,
            "model": model_id,
            "run": run_index,
            "description": description[:80],
            "status": status,
            "validation_error": validation_error,
            "review_issues": review_issues,
            "elapsed_seconds": round(elapsed, 2),
            "analysis": analysis,
            "lyric_file": lyric_file,
            "raw_preview": str(raw or "")[:800],
            "normalized_preview": normalized[:800],
            "normalized_full": normalized,
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
            "review_issues": [],
            "elapsed_seconds": round(elapsed, 2),
            "analysis": {},
            "lyric_file": None,
            "raw_preview": "",
            "normalized_preview": "",
            "normalized_full": "",
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
    parser.add_argument(
        "--lyrics-dir",
        default=str(REPO_ROOT / "docs" / "ai_free_probe_lyrics"),
        help="Directory to write full raw/normalized lyric files (empty to skip)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS_PER_MODEL,
        help="Number of generations per provider/model",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="Limit to specific provider(s); repeatable",
    )
    args = parser.parse_args()

    runs_per_model = max(1, int(args.runs))
    lyrics_dir = Path(args.lyrics_dir) if str(args.lyrics_dir).strip() else None

    await bootstrap_runtime()

    from platform_api.ai.registry import TEXT_MODEL_REGISTRY
    from platform_api.dependencies import get_generation_service, get_key_pool_service

    key_pool = get_key_pool_service()
    gateway = get_generation_service()._get_text_gateway()
    provider_filter = {p.strip().lower() for p in args.provider if p.strip()}

    results: list[dict[str, Any]] = []
    print("=" * 80)
    print("AI STRUCTURE FREE — provider probe (no structure template)")
    print(f"Runs per model: {runs_per_model}")
    print("=" * 80)

    for provider, models in TEXT_MODEL_REGISTRY.items():
        if provider_filter and provider.lower() not in provider_filter:
            continue
        pool_status = await key_pool.get_pool_status(provider)
        active_keys = int(pool_status.get("active_keys") or 0)
        if active_keys < 1:
            print(f"SKIP  {provider:10}  no active API keys")
            continue

        for model_id in models:
            for run_index in range(1, runs_per_model + 1):
                description = TEST_DESCRIPTIONS[(run_index - 1) % len(TEST_DESCRIPTIONS)]
                row = await probe_chat_provider(
                    gateway=gateway,
                    provider=provider,
                    model_id=model_id,
                    description=description,
                    run_index=run_index,
                    lyrics_dir=lyrics_dir,
                )
                results.append(row)
                status = row["status"]
                detail = row.get("validation_error") or (
                    "; ".join(row.get("review_issues") or [])
                    or (
                        f"headers={row['analysis'].get('header_count', 0)} "
                        f"lines={row['analysis'].get('content_line_count', 0)}"
                    )
                )
                print(
                    f"{status:5}  {row['elapsed_seconds']:5.1f}s  "
                    f"{provider:10}  {model_id:24}  run={run_index}  {str(detail)[:80]}"
                )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # JSON without full lyrics (keep file size manageable; full text in lyrics-dir).
    json_results = []
    for row in results:
        slim = dict(row)
        slim.pop("normalized_full", None)
        json_results.append(slim)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs_per_model": runs_per_model,
        "test_descriptions": TEST_DESCRIPTIONS,
        "lyrics_dir": str(lyrics_dir) if lyrics_dir else None,
        "results": json_results,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("-" * 80)
    print(f"Wrote {len(results)} probe rows to {output_path}")
    if lyrics_dir:
        print(f"Full lyrics in {lyrics_dir}")

    await shutdown_runtime()
    failures = sum(1 for row in results if row["status"] not in {"PASS", "WARN"})
    warns = sum(1 for row in results if row["status"] == "WARN")
    if warns:
        print(f"WARN: {warns} run(s) passed validation but flagged manual review issues")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
