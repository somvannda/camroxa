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

from platform_api.repositories.credit_repo import CreditRepository
from platform_api.repositories.model_cost_repo import ModelCostRepository
from platform_api.services.credit_pricing_service import CreditPricingService
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
        cost_service = ModelCostService(repo=ModelCostRepository(pool))
        pricing_service = CreditPricingService(pricing_repo=CreditRepository(pool))
        cost_result = await cost_service.seed_from_registry(overwrite=args.overwrite)
        pricing_result = await pricing_service.seed_local_platform_pricing(
            overwrite=args.overwrite
        )
        print(
            "Model costs seeded: "
            f"created/updated={cost_result['seeded_count']}, "
            f"skipped={cost_result['skipped_existing_count']}, "
            f"pruned={cost_result.get('pruned_count', 0)}"
        )
        print(
            "Local platform pricing seeded: "
            f"created={pricing_result['created_count']}, "
            f"updated={pricing_result['updated_count']}, "
            f"skipped={pricing_result['skipped_existing_count']}"
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
