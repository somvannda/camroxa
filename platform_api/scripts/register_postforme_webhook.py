"""Register the Post for Me webhook for publishing results.

Usage (from the repo root, with the platform API env loaded):

    python -m platform_api.scripts.register_postforme_webhook \\
        --url https://api.camxora.com/api/v3/publish/webhooks/postforme

Prints the webhook secret. Store it as PLATFORM_POSTFORME_WEBHOOK_SECRET.
The script is idempotent for the same URL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

EVENT_TYPES = [
    "social.post.result.created",
    "social.post.updated",
]


async def _run(url: str) -> int:
    from platform_api.config import get_settings
    from platform_api.services.postforme_client import PostForMeClient

    settings = get_settings()
    client = PostForMeClient(
        api_key=settings.postforme_api_key,
        base_url=settings.postforme_api_base_url,
        timeout_seconds=settings.postforme_timeout_seconds,
    )
    if not client.configured:
        print("PLATFORM_POSTFORME_API_KEY is not set.", file=sys.stderr)
        return 2

    existing = await client.list_webhooks()
    for hook in existing:
        if str(hook.get("url") or "").strip() == url:
            print(json.dumps({"existing": True, "id": hook.get("id"), "secret": hook.get("secret")}))
            return 0

    created = await client.create_webhook(url=url, event_types=EVENT_TYPES)
    print(json.dumps({"existing": False, **created}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("PLATFORM_POSTFORME_WEBHOOK_URL", "").strip(),
        help="Public webhook URL ending in /api/v3/publish/webhooks/postforme",
    )
    args = parser.parse_args()
    url = str(args.url or "").strip()
    if not url:
        print("--url or PLATFORM_POSTFORME_WEBHOOK_URL is required.", file=sys.stderr)
        return 2
    return asyncio.run(_run(url))


if __name__ == "__main__":
    raise SystemExit(main())
