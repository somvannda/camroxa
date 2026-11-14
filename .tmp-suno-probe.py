"""Live session probe: ask Suno for the account's billing with the stored cookie.

Read-only (no generation, no credits spent). Prints the HTTP status and a redacted summary
so we know whether a real stems job is possible right now.
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parent
ENV = ROOT / "musicapi" / ".env"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        values.setdefault(key, value)
    return values


async def main() -> None:
    env = load_env()
    db_url = env.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sunoapi")
    conn = await asyncpg.connect(db_url)
    row = await conn.fetchrow(
        """
        select id, label, client_cookie, is_active, credits_left
        from suno_accounts
        where client_cookie is not null
        order by credits_left desc nulls last
        limit 1
        """
    )
    await conn.close()
    if row is None:
        print("no account with a cookie")
        return
    print("account", row["label"], "active", row["is_active"], "credits", row["credits_left"])

    key = env.get("COOKIE_ENCRYPTION_KEY", "")
    cookie = row["client_cookie"]
    if cookie.startswith("enc:v1:"):
        try:
            raw = base64.b64decode(cookie.split("enc:v1:", 1)[1])
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            key_bytes = base64.b64decode(key) if len(key) % 4 == 0 else key.encode()
            if len(key_bytes) not in (16, 24, 32):
                key_bytes = key_bytes[:32].ljust(32, b"0")
            nonce, payload = raw[:12], raw[12:]
            cookie = AESGCM(key_bytes).decrypt(nonce, payload, None).decode()
        except Exception as exc:  # noqa: BLE001
            print("cookie decrypt failed:", str(exc)[:120])
            return

    headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        for url in (
            "https://studio-api.prod.suno.com/api/billing/info/",
            "https://studio-api.prod.suno.com/api/session/",
        ):
            try:
                response = await client.get(url, headers=headers)
                body = response.text[:200].replace("\n", " ")
                print(url, "->", response.status_code, body[:160])
            except Exception as exc:  # noqa: BLE001
                print(url, "failed:", str(exc)[:120])


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
