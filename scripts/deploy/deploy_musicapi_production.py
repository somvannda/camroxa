#!/usr/bin/env python3
"""Deploy the musicapi stack to the PRODUCTION VPS.

Same machinery as scripts/deploy/sync_musicapi_sandbox.py, but it reads
.deploy/secrets.production.env and refuses to run without an explicit --yes
(the Phase-4 gate: production only on an explicit ask).

Usage:
    python scripts/deploy/deploy_musicapi_production.py --yes
    python scripts/deploy/deploy_musicapi_production.py --yes --issue-cert
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_musicapi_sandbox import deploy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy the musicapi stack to the production VPS")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required: confirm you intend to deploy to PRODUCTION",
    )
    parser.add_argument(
        "--issue-cert",
        action="store_true",
        help="Bootstrap the Let's Encrypt cert on first deploy (DNS must resolve)",
    )
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to deploy to production without --yes.")
        print("Use scripts/deploy/sync_musicapi_sandbox.py for sandbox.")
        return 2
    return deploy("production", issue_cert=args.issue_cert)


if __name__ == "__main__":
    raise SystemExit(main())
