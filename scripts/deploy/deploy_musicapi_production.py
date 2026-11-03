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
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy_guards import enforce_deploy_gate  # noqa: E402
from sync_musicapi_sandbox import deploy  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def _best_effort_fetch() -> None:
    """Refresh origin/main so the gate's ancestry check is not fooled by a stale ref."""
    try:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "fetch", "--quiet", "origin", "main"],
            check=False,
            timeout=90,
        )
    except Exception as exc:  # pragma: no cover - network/optional
        print(f"[deploy-guard] WARN: git fetch failed ({exc}); using existing origin/main")


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
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Skip the Next.js frontend builds (core API + migrations + services only)",
    )
    args = parser.parse_args()

    if not args.yes:
        print("Refusing to deploy to production without --yes.")
        print("Use scripts/deploy/sync_musicapi_sandbox.py for sandbox.")
        return 2

    # Production must ship a committed, merged revision. A deploy from a dirty
    # worktree or an unmerged branch silently rewrote the server's .env from an
    # arbitrary tree — this wiped the SUNO_* concurrency caps twice on
    # 2026-10-07. require_merged makes a tag on a feature branch insufficient;
    # the clean-worktree check keeps the packaged files equal to that commit.
    # Override a deliberate hotfix with CAMXORA_ALLOW_DIRTY_DEPLOY=1 /
    # CAMXORA_ALLOW_UNMERGED_DEPLOY=1.
    _best_effort_fetch()
    enforce_deploy_gate(require_merged=True)

    # The musicapi deploy packages the working tree, so require HEAD to be the
    # tip of main: a clean checkout of an older, still-merged commit would ship
    # old code just as happily. Override deliberately with
    # CAMXORA_ALLOW_STALE_SOURCE=1.
    _refuse_stale_musicapi_source()

    return deploy("production", issue_cert=args.issue_cert, skip_frontend=args.api_only)


def _refuse_stale_musicapi_source() -> None:
    import os

    from release_source import DEFAULT_SOURCE_REF, resolve_source_commit

    if os.environ.get("CAMXORA_ALLOW_STALE_SOURCE", "").strip() == "1":
        print("[deploy-guard] WARNING: stale-source override set — shipping HEAD as-is")
        return
    head = resolve_source_commit(REPO_ROOT, "HEAD")
    tip = resolve_source_commit(REPO_ROOT, DEFAULT_SOURCE_REF)
    if head != tip:
        raise SystemExit(
            "Refusing deploy — musicapi ships the working tree, and HEAD "
            f"{head[:8]} is not the tip of {DEFAULT_SOURCE_REF} ({tip[:8]}).\n"
            "Run `git switch main && git pull --ff-only`, or deploy the platform "
            "from origin/main instead (scripts/deploy/deploy_production.py).\n"
            "Deliberate override: CAMXORA_ALLOW_STALE_SOURCE=1."
        )
    print(f"[deploy-guard] musicapi source {head[:8]} is the tip of {DEFAULT_SOURCE_REF}")


if __name__ == "__main__":
    raise SystemExit(main())
