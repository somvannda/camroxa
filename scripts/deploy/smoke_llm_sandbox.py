#!/usr/bin/env python3
"""Smoke-test DeepSeek and OpenAI text on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

REMOTE = r"""
sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && set +a && PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<"PY"
import asyncio
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
PY'
"""


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    _, stdout, stderr = client.exec_command(REMOTE)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
