"""Print the local Admin → v3 parity checklist (same DB, two API doors).

Does not mutate production. Optional: pass --base-url and --token to hit a live API.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


CHECKS = [
    "Admin Credits music/lyric prices -> POST /api/v3/billing/quote uses credit_pricing when plan per-op is null",
    "PATCH /api/v3/admin/plans/{id} music_credits=10 -> quote for that licensed user becomes 10",
    "POST /api/v1/credits/adjust +10 -> GET /api/v3/me/credits (or /users/{id}/credits) matches v1 balance",
    "Fail-absorb refund via POST /api/v3/billing/refund absorb=true increments the same counter Admin user-detail shows",
    "GET /api/v1/plans/public JSON shape unchanged (no music_credits / monthly_credits fields)",
    "GET /api/v3/plans/public returns only is_active AND is_public rows",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="")
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    print("Credits-only v3 admin parity")
    for index, line in enumerate(CHECKS, start=1):
        print(f"{index}. {line}")
    if not args.base_url:
        return 0
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    for path in ("/api/v3/docs", "/api/v3/plans/public", "/api/v1/plans/public"):
        url = args.base_url.rstrip("/") + path
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                print(f"OK {response.status} {path}")
                if path.endswith("/public"):
                    body = json.loads(response.read().decode())
                    print(f"   rows={len(body)}")
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code} {path}", file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"FAIL {path}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
