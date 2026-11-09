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
    parser.add_argument(
        "--verify-live",
        action="store_true",
        help="also re-hash the live checkout against its .deploy-manifest.json",
    )
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
        if args.verify_live:
            verify_live_source(client, args.remote_repo)
    finally:
        client.close()
    print("[deploy-guard] OK — worktree deployable and server invariants present.")
    return 0


def live_source_status(client, remote_repo: str) -> tuple[str, str]:
    """Return (status, detail) for the live checkout vs its deployed manifest.

    status: ``ok`` | ``drift`` | ``no-manifest``.
    """
    from deploy import upload_verifier
    from deploy_guards import deployed_marker_path

    marker_path = deployed_marker_path(remote_repo)
    sftp = client.open_sftp()
    try:
        with sftp.file(marker_path, "r") as handle:
            marker = handle.read().decode("utf-8", "replace")
    except OSError:
        return "no-manifest", f"no {marker_path} (not deployed through the verified pipeline)"
    finally:
        sftp.close()

    upload_verifier(client)
    _, stdout, _stderr = client.exec_command(
        "python3 /tmp/camxora-verify-manifest.py "
        f"--repo {remote_repo} --manifest {remote_repo}/.deploy-manifest.json"
    )
    output = stdout.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return ("ok" if code == 0 else "drift"), f"{marker.strip()}\n{output.strip()}"


def verify_live_source(client, remote_repo: str) -> None:
    """Fail unless the live checkout still matches the deployed manifest.

    Detects a server-side hotfix, a partial write, or a deploy that skipped the
    manifest step — the drift that used to go unnoticed until a later deploy
    "reverted" the change.
    """
    status, detail = live_source_status(client, remote_repo)
    print("[deploy-guard] live marker / verification:")
    print(detail)
    if status == "no-manifest":
        raise SystemExit(
            f"Refusing: {detail} — the live source was not deployed through the "
            "verified pipeline."
        )
    if status == "drift":
        raise SystemExit(
            "Refusing: the live checkout does not match the deployed manifest — "
            "someone edited production in place. Deploy merged main to restore it."
        )


if __name__ == "__main__":
    raise SystemExit(main())
