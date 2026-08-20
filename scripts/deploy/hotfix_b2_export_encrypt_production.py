#!/usr/bin/env python3
"""File-scoped production hotfix: Music-only leftover encrypt (skip Studio).

Allowlisted API paths only. Host must be 82.197.71.248.
Does not tar the tree, does not run alembic, does not touch sandbox.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    CANONICAL_PRODUCTION_HOST,
    CANONICAL_SANDBOX_HOST,
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

API_FILES = [
    "platform_api/services/audio_package_service.py",
    "platform_api/services/streaming_upload_service.py",
]


def _run(client, cmd: str, timeout: int = 180) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out + ("\n" + err if err.strip() else "")


def _upload(client, sftp, rels: list[str]) -> None:
    for rel in rels:
        local = ROOT / rel
        if not local.is_file():
            raise SystemExit(f"Missing source file: {rel}")
        remote = f"/opt/camxora/repo/{rel}".replace("\\", "/")
        parent = remote.rsplit("/", 1)[0]
        _, stdout, _ = client.exec_command(f"mkdir -p {parent}")
        stdout.channel.recv_exit_status()
        print(f"Uploading {rel}", flush=True)
        sftp.put(str(local), remote)


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    print(f"Target production host: {host}", flush=True)
    if host != CANONICAL_PRODUCTION_HOST or host == CANONICAL_SANDBOX_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        _upload(client, sftp, API_FILES)
        sftp.close()
        chown = " ".join(f"/opt/camxora/repo/{p}" for p in API_FILES)
        code, out = _run(
            client,
            rf"""
set -e
chown camxora:camxora {chown}
systemctl restart camxora-api
code=""
for i in 1 2 3 4 5 6 7 8 9 10 12 14 16 18 20; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{{http_code}}' http://127.0.0.1:8100/health || true)
  echo attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
echo EXPORT_ENCRYPT_HOTFIX_OK
""",
        )
        print(out, flush=True)
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
