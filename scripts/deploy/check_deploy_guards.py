#!/usr/bin/env python3
"""Preflight: verify this worktree can be deployed and the live server is intact.

    python scripts/deploy/check_deploy_guards.py                 # production
    python scripts/deploy/check_deploy_guards.py sandbox
    python scripts/deploy/check_deploy_guards.py production --allow-dirty

Fails (non-zero) when the worktree is dirty, HEAD is not tagged/merged to the base
ref, or any critical runtime invariant is missing on the target server.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    load_sandbox_secrets,
    resolve_production_ssh,
    resolve_sandbox_ssh,
    ssh_connect,
)
from deploy_guards import (  # noqa: E402
    DEFAULT_REMOTE_REPO,
    enforce_deploy_gate,
    enforce_invariants,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="production")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--allow-unmerged", action="store_true")
    parser.add_argument("--base-ref", default=None)
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    args = parser.parse_args()

    target = args.target.strip().lower()
    if target.startswith("s"):
        secrets = load_sandbox_secrets()
        host, user, password = resolve_sandbox_ssh(secrets)
        label = "sandbox"
    else:
        secrets = load_production_secrets()
        host, user, password = resolve_production_ssh(secrets)
        label = "production"

    gate = enforce_deploy_gate(
        base_ref=args.base_ref,
        allow_dirty=args.allow_dirty,
        allow_unmerged=args.allow_unmerged,
    )
    print(
        f"[deploy-guard] {label}: HEAD {gate.state.short} clean="
        f"{not gate.state.dirty} merged={gate.merged}"
    )

    print(f"Checking runtime invariants on {label} ({host}) ...")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        enforce_invariants(client, args.remote_repo)
    finally:
        client.close()
    print("[deploy-guard] OK — worktree deployable and server invariants present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
