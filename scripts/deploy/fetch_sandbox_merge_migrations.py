#!/usr/bin/env python3
"""Fetch Alembic merge migration files present on sandbox but missing locally."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_sandbox_secrets, resolve_sandbox_ssh, ssh_connect

REMOTE_DIR = "/opt/camxora/repo/platform_api/migrations/versions"
LOCAL_DIR = Path(__file__).resolve().parents[2] / "platform_api" / "migrations" / "versions"

PATTERNS = [
    "*merge_web_music*",
    "1f0ad008d202*.py",
]


def main() -> int:
    secrets = load_sandbox_secrets()
    host, user, password = resolve_sandbox_ssh(secrets)
    client = ssh_connect(host, user, ensure_deploy_key(), password)

    list_cmd = (
        f"sudo -u camxora bash -lc 'ls {REMOTE_DIR}/*merge_web_music* "
        f"{REMOTE_DIR}/1f0ad008d202*.py 2>/dev/null'"
    )
    _, stdout, _ = client.exec_command(list_cmd, get_pty=True)
    stdout.channel.recv_exit_status()
    remote_files = [
        line.strip()
        for line in stdout.read().decode("utf-8", errors="replace").splitlines()
        if line.strip().endswith(".py")
    ]

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    for remote_path in remote_files:
        name = Path(remote_path).name
        local_path = LOCAL_DIR / name
        if local_path.is_file():
            print(f"skip existing {name}")
            continue
        _, out, _ = client.exec_command(f"sudo -u camxora cat {remote_path}")
        out.channel.recv_exit_status()
        content = out.read().decode("utf-8", errors="replace")
        local_path.write_text(content, encoding="utf-8")
        print(f"fetched {name}")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
