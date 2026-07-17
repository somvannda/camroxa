#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")

from platform_api.dependencies import get_db_pool
from platform_api.repositories.key_pool_repo import KeyPoolRepository
from platform_api.services.key_pool_service import KeyPoolService
from platform_api.ai.providers.text.gateway import TextProviderGateway


async def try_provider(provider, model):
    pool = get_db_pool()
    svc = KeyPoolService(KeyPoolRepository(pool=pool))
    gw = TextProviderGateway(key_pool_service=svc)
    try:
        text = await gw.generate_text(
            provider=provider,
            model=model,
            system_prompt="Reply with JSON array only.",
            user_prompt='Return ["TestName"]',
            temperature=0.2,
            max_tokens=100,
            prefer_json=True,
        )
        print(provider, model, "OK", text[:80])
    except Exception as exc:
        print(provider, model, "FAIL", type(exc).__name__, str(exc)[:200])


async def main():
    from platform_api.main import app

    async with app.router.lifespan_context(app):
        for provider, model in [
            ("deepseek", "deepseek-chat"),
            ("openai", "gpt-4o-mini"),
            ("slai", "xiaomi/mimo-v2.5-pro"),
        ]:
            await try_provider(provider, model)


asyncio.run(main())
