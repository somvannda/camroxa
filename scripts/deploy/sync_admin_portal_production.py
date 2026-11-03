#!/usr/bin/env python3
"""Sync admin_portal to production and rebuild — from one commit of main.

Previously this packaged the local ``admin_portal`` directory and tar'd it over
``/opt/camxora/repo``, which is the same stale-source bug the platform deploy
had. It now packages ``origin/main``, verifies the manifest on the server before
building, and prunes files the previous deploy shipped that this one does not.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import (  # noqa: E402
    build_source_bundle,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
    upload_verifier,
)
from deploy_guards import (  # noqa: E402
    acquire_remote_lock,
    enforce_deploy_gate,
    post_deploy_record,
    release_remote_lock,
)
from release_source import DEFAULT_SOURCE_REF, SOURCE_MODE_ENV  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"


def _run(client, cmd: str) -> int:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    sys.stdout.buffer.write((out[-5000:] if len(out) > 5000 else out).encode("utf-8", "replace") + b"\n")
    if err.strip():
        sys.stdout.buffer.write(err[-2000:].encode("utf-8", "replace") + b"\n")
    return code


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Target production host: {host}")

    bundle = build_source_bundle(DEFAULT_SOURCE_REF)
    mode = os.environ.get(SOURCE_MODE_ENV, "commit").strip().lower()
    gate = enforce_deploy_gate(
        commit=bundle.commit,
        require_merged=True,
        require_clean=(mode == "worktree"),
    )

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    lock = acquire_remote_lock(client)
    try:
        sftp = client.open_sftp()
        with sftp.file("/tmp/camxora-src.tar.gz", "wb") as remote_file:
            remote_file.write(bundle.path.read_bytes())
        sftp.close()
        upload_verifier(client)

        code = _run(
            client,
            r"""
set -e
REPO=/opt/camxora/repo
cp -f "$REPO/.deploy-manifest.json" "$REPO/.deploy-manifest.prev.json" 2>/dev/null || true
tar -xzf /tmp/camxora-src.tar.gz -C $REPO admin_portal .deploy-manifest.json
python3 /tmp/camxora-verify-manifest.py \
  --repo $REPO \
  --manifest $REPO/.deploy-manifest.json \
  --scope admin_portal \
  --prev-manifest $REPO/.deploy-manifest.prev.json
rm -f $REPO/.deploy-manifest.prev.json
chown -R camxora:camxora $REPO/admin_portal
sudo -u camxora bash -lc 'cd /opt/camxora/repo/admin_portal && (npm ci || npm install --no-audit --no-fund) && npm run build'
echo ADMIN_SYNC_DONE
""",
        )
        if code == 0:
            post_deploy_record(
                client,
                gate,
                target="production",
                script=Path(__file__).name,
                extra={
                    "source_commit": bundle.commit,
                    "source_ref": bundle.ref,
                    "source_mode": bundle.mode,
                    "source_files": bundle.files,
                    "manifest": ".deploy-manifest.json",
                    "scope": "admin_portal",
                },
            )
    finally:
        release_remote_lock(client, lock)
        client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
