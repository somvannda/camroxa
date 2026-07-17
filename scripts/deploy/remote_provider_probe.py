#!/usr/bin/env python3
import asyncio
import json
import os
import sys

import asyncpg
import httpx

sys.path.insert(0, "/opt/camxora/repo")
from platform_api.services.key_encryption import KeyEncryption


async def main() -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(dsn)
    enc = KeyEncryption(os.environ.get("PLATFORM_ENCRYPTION_MASTER_KEY", ""))
    rows = await conn.fetch(
        "SELECT provider, label, encrypted_key_value FROM api_key_entries WHERE status='active' ORDER BY provider"
    )
    await conn.close()

    for row in rows:
        provider = row["provider"]
        try:
            api_key = enc.decrypt(row["encrypted_key_value"])
        except Exception as exc:
            print(provider, "decrypt_FAIL", exc)
            continue

        if provider == "deepseek":
            url = "https://api.deepseek.com/chat/completions"
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": 'Return JSON: ["TestName"]'}],
                "max_tokens": 50,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": 'Return JSON: ["TestName"]'}],
                "max_tokens": 50,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        elif provider == "slai":
            url = os.environ.get("PLATFORM_SLAI_API_BASE_URL", "https://api.slai.io/v1").rstrip("/") + "/chat/completions"
            payload = {
                "model": "xiaomi/mimo-v2.5-pro",
                "messages": [{"role": "user", "content": 'Return JSON: ["TestName"]'}],
                "max_tokens": 50,
            }
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        else:
            continue

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
            print(provider, resp.status_code, resp.text[:160].replace("\n", " "))
        except Exception as exc:
            print(provider, "HTTP_FAIL", type(exc).__name__, str(exc)[:160])


asyncio.run(main())
