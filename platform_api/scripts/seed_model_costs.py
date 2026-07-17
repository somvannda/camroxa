"""Re-seed ai_model_costs from the model registry.

Usage:
    python -m platform_api.scripts.seed_model_costs
    python -m platform_api.scripts.seed_model_costs --overwrite
"""

from __future__ import annotations

import argparse
import asyncio
import os

import asyncpg

from platform_api.repositories.model_cost_repo import ModelCostRepository
from platform_api.services.model_cost_service import ModelCostService


DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/platform_db"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed model costs from registry")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing registry rows with fresh estimates",
    )
    args = parser.parse_args()

    dsn = os.environ.get("PLATFORM_DATABASE_URL", DEFAULT_DATABASE_URL)
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    pool = await asyncpg.create_pool(dsn)
    try:
        service = ModelCostService(repo=ModelCostRepository(pool))
        result = await service.seed_from_registry(overwrite=args.overwrite)
        print(
            "Model costs seeded: "
            f"created/updated={result['seeded_count']}, "
            f"skipped={result['skipped_existing_count']}, "
            f"pruned={result.get('pruned_count', 0)}"
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
