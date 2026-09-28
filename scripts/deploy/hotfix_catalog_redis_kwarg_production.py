#!/usr/bin/env python3
"""File-scoped production hotfix: StreamingCatalogService accepts redis=."""

from __future__ import annotations

import sys
import time
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[2]
HOST_REPO = Path(r"G:\Developments\Projects\Camxora\MusicGenerator")
if not (HOST_REPO / ".deploy" / "secrets.production.env").is_file():
    HOST_REPO = CODE_ROOT
DEPLOY = HOST_REPO / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (  # noqa: E402
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"
FILES = ["platform_api/services/streaming_catalog_service.py"]


def _run(client, cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=timeout)
    while not stdout.channel.exit_status_ready():
        time.sleep(0.2)
    return stdout.read().decode("utf-8", errors="replace") + stderr.read().decode(
        "utf-8", errors="replace"
    )


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"=== catalog redis kwarg -> production ({host}) ===", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = CODE_ROOT / rel
            remote = f"/opt/camxora/repo/{rel.replace(chr(92), '/')}"
            payload = local.read_bytes().replace(b"\r\n", b"\n")
            with sftp.file(remote, "wb") as rf:
                rf.write(payload)
            print(f"Uploaded {rel}", flush=True)
        sftp.close()
        out = _run(
            client,
            r"""
set -e
chown camxora:camxora /opt/camxora/repo/platform_api/services/streaming_catalog_service.py
python3 -m py_compile /opt/camxora/repo/platform_api/services/streaming_catalog_service.py
grep -n 'redis: Any' /opt/camxora/repo/platform_api/services/streaming_catalog_service.py | head
systemctl restart camxora-api
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code=$(curl -sS -m 3 -o /tmp/prod_health.json -w '%{http_code}' http://127.0.0.1:8100/health || true)
  echo api_attempt_$i health=$code
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
test "$code" = "200"
curl -sS -m 8 -w '\nlikes_ids=%{http_code}\n' http://127.0.0.1:8100/api/v1/streaming/library/likes/ids | tail -5
echo CATALOG_REDIS_PRODUCTION_DONE
""",
            timeout=90,
        )
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if "CATALOG_REDIS_PRODUCTION_DONE" not in out:
            raise SystemExit("Production hotfix did not finish cleanly.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
